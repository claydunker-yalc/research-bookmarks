from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from models import (
    ArticleCreate, ArticleManualCreate, ArticleResponse, ArticleExport,
    SearchRequest, SearchResult, SynthesizeRequest, SynthesisResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse, CategoryWithStats,
    CategoryDigestPreview, DiscoveredTheme
)
from urllib.parse import urlparse
from database import (
    check_url_exists,
    insert_article,
    get_all_articles,
    get_article_by_id,
    search_by_embedding,
    get_articles_by_ids,
    get_recent_articles,
    get_random_older_articles,
    get_article_count,
    insert_quotes_batch,
    get_all_quotes_with_articles,
    get_quote_count,
    get_articles_without_quotes,
    article_has_quotes,
    get_recent_digest_anchor_ids,
    save_digest_history,
    delete_quotes_for_article,
    get_all_articles_with_text,
    # Category functions
    get_all_categories,
    get_queued_categories,
    get_pool_categories,
    move_category_to_pool,
    get_category_by_id,
    insert_category,
    update_category,
    delete_category,
    get_themes_from_digest_history,
    update_category_last_digest
)
from services import (
    extract_article,
    generate_summary,
    generate_embedding,
    synthesize_articles,
    generate_curator_digest,
    send_digest_email,
    is_email_configured,
    extract_quotes
)
from services.category_matcher import generate_category_embedding, get_category_stats
from services.digest_generator import generate_digest_for_category
from services.article_extractor import ExtractionError

# Scheduler for periodic digest emails
scheduler = BackgroundScheduler(timezone=pytz.timezone('America/Chicago'))


def extract_and_store_quotes(article_id: str, article_text: str, article_title: str):
    """Background task to extract quotes from an article and store them."""
    try:
        # Use thorough=True for multi-theme extraction (5-10 quotes per article)
        quotes = extract_quotes(article_text, article_title, thorough=True)
        if quotes:
            # Generate embeddings for each quote
            quotes_with_embeddings = []
            for q in quotes:
                embedding = generate_embedding(q['quote_text'])
                quotes_with_embeddings.append({
                    'article_id': article_id,
                    'quote_text': q['quote_text'],
                    'embedding': embedding
                })
            insert_quotes_batch(quotes_with_embeddings)
            print(f"Extracted {len(quotes_with_embeddings)} quotes from article {article_id}")
    except Exception as e:
        print(f"Quote extraction failed for {article_id}: {e}")


def send_scheduled_digest():
    """Background task to send curator's pick digest email."""
    if not is_email_configured():
        print("Email not configured, skipping digest")
        return

    try:
        # Get all quotes with article metadata
        quotes = get_all_quotes_with_articles()

        if not quotes:
            print("No quotes available for digest, skipping")
            return

        digest = None
        category_used = None

        # Check for queued categories first (user-requested themes get priority)
        queued = get_queued_categories()
        if queued:
            category = queued[0]  # Oldest queued category
            print(f"Found queued category: '{category['name']}'")

            digest = generate_digest_for_category(category, quotes)
            if digest:
                category_used = category
            else:
                print(f"Not enough matching quotes for category '{category['name']}', using auto-discovery")

        # If no queued category worked, use auto-discovery
        if not digest:
            excluded_anchors = get_recent_digest_anchor_ids(days=7)
            digest = generate_curator_digest(quotes, excluded_anchor_ids=excluded_anchors)

        if digest:
            send_digest_email(digest["subject"], digest["html_body"])

            # Save to history
            save_digest_history(
                theme=digest.get("theme"),
                anchor_quote_id=digest.get("anchor_quote_id"),
                anchor_article_id=digest.get("anchor_article_id"),
                cluster_quote_ids=digest.get("cluster_quote_ids", [])
            )

            # If we used a queued category, move it to the pool
            if category_used:
                move_category_to_pool(category_used['id'])
                update_category_last_digest(category_used['id'])
                print(f"Category '{category_used['name']}' moved to pool")

            print(f"Curator digest sent: theme='{digest.get('theme')}'")
        else:
            print("No suitable quote cluster found for digest")
    except Exception as e:
        print(f"Failed to send digest: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start scheduler if email is configured
    if is_email_configured():
        # Schedule daily curator digest at 9:45 AM Central
        # This now also processes queued categories with priority
        scheduler.add_job(
            send_scheduled_digest,
            CronTrigger(hour=9, minute=45, timezone=pytz.timezone('America/Chicago')),
            id="curator_digest",
            replace_existing=True
        )

        scheduler.start()
        print("Digest scheduler started: daily at 9:45 AM Central")
        print("  (Queued categories get priority, then auto-discovery)")
    else:
        print("Email not configured, digest scheduler not started")
    yield
    # Shutdown: stop scheduler
    if scheduler.running:
        scheduler.shutdown()

app = FastAPI(
    title="Research Bookmarks API",
    description="Save and semantically search research articles",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Research Bookmarks API", "version": "1.0.0"}


@app.post("/articles", response_model=ArticleResponse)
async def save_article(article: ArticleCreate, background_tasks: BackgroundTasks):
    """
    Save a new article by URL.

    1. Check for duplicates
    2. Extract article content
    3. Generate AI summary
    4. Generate embedding for semantic search
    5. Store in database
    6. Extract quotes in background
    """
    url = str(article.url)

    existing = check_url_exists(url)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Article already exists",
                "existing_article": {
                    "id": existing["id"],
                    "title": existing.get("title"),
                    "created_at": existing.get("created_at")
                }
            }
        )

    try:
        extracted = extract_article(url)
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    summary = generate_summary(extracted["clean_text"], extracted["title"])

    text_for_embedding = f"{extracted['title'] or ''} {extracted['clean_text']}"
    embedding = generate_embedding(text_for_embedding)

    article_data = {
        "url": url,
        "title": extracted["title"],
        "clean_text": extracted["clean_text"],
        "summary": summary,
        "domain": extracted["domain"],
        "embedding": embedding
    }

    saved = insert_article(article_data)

    # Extract quotes in background
    background_tasks.add_task(
        extract_and_store_quotes,
        saved["id"],
        extracted["clean_text"],
        extracted["title"]
    )

    return ArticleResponse(
        id=saved["id"],
        url=saved["url"],
        title=saved.get("title"),
        summary=saved.get("summary"),
        domain=saved.get("domain"),
        created_at=saved["created_at"]
    )


@app.post("/articles/manual", response_model=ArticleResponse)
async def save_article_manual(article: ArticleManualCreate, background_tasks: BackgroundTasks):
    """
    Manually save an article with pasted content.
    Use this for paywalled or scraper-resistant sites.
    """
    url = str(article.url)

    existing = check_url_exists(url)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Article already exists",
                "existing_article": {
                    "id": existing["id"],
                    "title": existing.get("title"),
                    "created_at": existing.get("created_at")
                }
            }
        )

    if len(article.content.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Article content too short. Please paste at least 100 characters."
        )

    domain = urlparse(url).netloc.replace("www.", "")

    summary = generate_summary(article.content, article.title)

    text_for_embedding = f"{article.title} {article.content}"
    embedding = generate_embedding(text_for_embedding)

    article_data = {
        "url": url,
        "title": article.title,
        "clean_text": article.content,
        "summary": summary,
        "domain": domain,
        "embedding": embedding
    }

    saved = insert_article(article_data)

    # Extract quotes in background
    background_tasks.add_task(
        extract_and_store_quotes,
        saved["id"],
        article.content,
        article.title
    )

    return ArticleResponse(
        id=saved["id"],
        url=saved["url"],
        title=saved.get("title"),
        summary=saved.get("summary"),
        domain=saved.get("domain"),
        created_at=saved["created_at"]
    )


@app.get("/articles", response_model=list[ArticleResponse])
async def list_articles(limit: int = 50, offset: int = 0):
    """Get all saved articles, ordered by newest first."""
    articles = get_all_articles(limit=limit, offset=offset)
    return [
        ArticleResponse(
            id=a["id"],
            url=a["url"],
            title=a.get("title"),
            summary=a.get("summary"),
            domain=a.get("domain"),
            created_at=a["created_at"]
        )
        for a in articles
    ]


@app.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str):
    """Get a single article by ID."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return ArticleResponse(
        id=article["id"],
        url=article["url"],
        title=article.get("title"),
        summary=article.get("summary"),
        domain=article.get("domain"),
        created_at=article["created_at"]
    )


@app.post("/articles/export", response_model=list[ArticleExport])
async def export_articles(article_ids: list[str]):
    """
    Export articles with full text for NotebookLM and similar tools.

    Returns complete article data including clean_text for each article ID.
    """
    if not article_ids:
        raise HTTPException(status_code=400, detail="No article IDs provided")
    if len(article_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 articles per export")

    articles = get_articles_by_ids(article_ids)

    if not articles:
        raise HTTPException(status_code=404, detail="No articles found")

    return [
        ArticleExport(
            id=a["id"],
            url=a["url"],
            title=a.get("title"),
            summary=a.get("summary"),
            clean_text=a.get("clean_text"),
            domain=a.get("domain"),
            created_at=a["created_at"]
        )
        for a in articles
    ]


@app.post("/search", response_model=list[SearchResult])
async def search_articles(request: SearchRequest):
    """
    Semantic search for articles.

    Generates an embedding for the search query and finds
    articles with similar embeddings using cosine similarity.
    """
    query_embedding = generate_embedding(request.query)

    results = search_by_embedding(query_embedding, limit=request.limit)

    return [
        SearchResult(
            id=r["id"],
            url=r["url"],
            title=r.get("title"),
            summary=r.get("summary"),
            domain=r.get("domain"),
            created_at=r["created_at"],
            similarity=r["similarity"]
        )
        for r in results
    ]


@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize(request: SynthesizeRequest):
    """
    Synthesize multiple articles into a research brief.

    Takes a list of article IDs and a focus topic, retrieves the full
    article text, and uses Claude to create a synthesis.
    """
    if len(request.article_ids) < 1:
        raise HTTPException(status_code=400, detail="At least 1 article required")
    if len(request.article_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 articles allowed")

    articles = get_articles_by_ids(request.article_ids)

    if not articles:
        raise HTTPException(status_code=404, detail="No articles found")

    synthesis = synthesize_articles(articles, request.focus_topic)

    sources = [
        {"id": a["id"], "title": a.get("title"), "url": a.get("url"), "domain": a.get("domain")}
        for a in articles
    ]

    return SynthesisResponse(
        focus_topic=request.focus_topic,
        summary=synthesis,
        sources=sources
    )


@app.get("/digest/status")
async def digest_status():
    """Check if email digest is configured and get scheduler status."""
    return {
        "email_configured": is_email_configured(),
        "scheduler_running": scheduler.running if scheduler else False,
        "total_articles": get_article_count(),
        "total_quotes": get_quote_count(),
        "schedule": "Daily at 9:45 AM Central"
    }


@app.get("/digest/preview")
async def preview_digest():
    """Preview what the curator's pick digest would contain without sending."""
    quotes = get_all_quotes_with_articles()

    if not quotes:
        return {
            "message": "No quotes available. Run /quotes/backfill to extract quotes from existing articles.",
            "total_quotes": 0
        }

    # Get recently used anchor IDs to show what would be picked next
    excluded_anchors = get_recent_digest_anchor_ids(days=7)

    digest = generate_curator_digest(quotes, excluded_anchor_ids=excluded_anchors)

    if not digest:
        return {
            "message": "No suitable quote cluster found. Need 5+ related quotes from 3+ articles.",
            "total_quotes": len(quotes)
        }

    return {
        "subject": digest["subject"],
        "theme": digest.get("theme"),
        "anchor_article": digest.get("anchor_article"),
        "recent_count": digest.get("recent_count"),
        "total_quotes": len(quotes),
        "html_preview": digest["html_body"]
    }


@app.post("/digest/send")
async def send_digest():
    """Manually trigger sending the curator's pick digest email."""
    if not is_email_configured():
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Set RESEND_API_KEY and USER_EMAIL environment variables."
        )

    quotes = get_all_quotes_with_articles()

    if not quotes:
        raise HTTPException(
            status_code=400,
            detail="No quotes available. Run POST /quotes/backfill to extract quotes from existing articles."
        )

    # Get recently used anchor IDs to avoid repetition
    excluded_anchors = get_recent_digest_anchor_ids(days=7)

    digest = generate_curator_digest(quotes, excluded_anchor_ids=excluded_anchors)
    if not digest:
        raise HTTPException(
            status_code=400,
            detail="No suitable quote cluster found. Need 5+ related quotes from 3+ articles."
        )

    try:
        result = send_digest_email(digest["subject"], digest["html_body"])

        # Save to history to avoid repeating this theme
        save_digest_history(
            theme=digest.get("theme"),
            anchor_quote_id=digest.get("anchor_quote_id"),
            anchor_article_id=digest.get("anchor_article_id"),
            cluster_quote_ids=digest.get("cluster_quote_ids", [])
        )

        return {
            "success": True,
            "message": f"Curator's pick sent: '{digest.get('theme')}'",
            "theme": digest.get("theme"),
            "anchor_article": digest.get("anchor_article"),
            "email_id": result.get("id")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@app.get("/quotes/status")
async def quotes_status():
    """Get quote extraction status."""
    articles_without = get_articles_without_quotes()
    return {
        "total_quotes": get_quote_count(),
        "total_articles": get_article_count(),
        "articles_without_quotes": len(articles_without),
        "articles_needing_backfill": [
            {"id": a["id"], "title": a.get("title")}
            for a in articles_without[:10]  # Show first 10
        ]
    }


@app.post("/quotes/backfill")
async def backfill_quotes(background_tasks: BackgroundTasks, limit: int = 10):
    """
    Extract quotes from existing articles that don't have quotes yet.
    Runs in background to avoid timeout.
    """
    articles = get_articles_without_quotes()

    if not articles:
        return {"message": "All articles already have quotes extracted", "processed": 0}

    # Process up to 'limit' articles
    to_process = articles[:limit]

    for article in to_process:
        background_tasks.add_task(
            extract_and_store_quotes,
            article["id"],
            article.get("clean_text", ""),
            article.get("title", "")
        )

    return {
        "message": f"Started quote extraction for {len(to_process)} articles",
        "processing": [{"id": a["id"], "title": a.get("title")} for a in to_process],
        "remaining": len(articles) - len(to_process)
    }


def reextract_quotes_for_article(article_id: str, article_text: str, article_title: str):
    """Background task to delete old quotes and extract new ones with thorough mode."""
    try:
        # Delete existing quotes
        deleted = delete_quotes_for_article(article_id)
        print(f"Deleted {deleted} old quotes from article {article_id}")

        # Extract new quotes with thorough=True for multi-theme coverage
        quotes = extract_quotes(article_text, article_title, thorough=True)
        if quotes:
            # Generate embeddings for each quote
            quotes_with_embeddings = []
            for q in quotes:
                embedding = generate_embedding(q['quote_text'])
                quotes_with_embeddings.append({
                    'article_id': article_id,
                    'quote_text': q['quote_text'],
                    'embedding': embedding
                })
            insert_quotes_batch(quotes_with_embeddings)
            print(f"Extracted {len(quotes_with_embeddings)} new quotes from article {article_id}")
    except Exception as e:
        print(f"Re-extraction failed for {article_id}: {e}")


@app.post("/quotes/reextract")
async def reextract_all_quotes(background_tasks: BackgroundTasks, limit: int = 10):
    """
    Re-extract quotes from ALL articles with thorough multi-theme extraction.

    This replaces existing quotes with new ones that cover more themes.
    Use this to upgrade your quote library for better thematic diversity.
    Runs in background to avoid timeout.
    """
    articles = get_all_articles_with_text()

    if not articles:
        return {"message": "No articles found", "processed": 0}

    # Process up to 'limit' articles
    to_process = articles[:limit]

    for article in to_process:
        background_tasks.add_task(
            reextract_quotes_for_article,
            article["id"],
            article.get("clean_text", ""),
            article.get("title", "")
        )

    return {
        "message": f"Started thorough re-extraction for {len(to_process)} articles",
        "processing": [{"id": a["id"], "title": a.get("title")} for a in to_process],
        "remaining": len(articles) - len(to_process),
        "note": "Each article will now have 5-10 quotes covering different themes"
    }


@app.post("/quotes/reextract/{article_id}")
async def reextract_single_article(article_id: str, background_tasks: BackgroundTasks):
    """Re-extract quotes for a single article with thorough multi-theme extraction."""
    article = get_article_by_id(article_id)

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    background_tasks.add_task(
        reextract_quotes_for_article,
        article["id"],
        article.get("clean_text", ""),
        article.get("title", "")
    )

    return {
        "message": f"Started thorough re-extraction for '{article.get('title')}'",
        "article_id": article_id
    }


@app.post("/quotes/reextract-sync")
async def reextract_all_quotes_sync(limit: int = 50, offset: int = 0):
    """
    Re-extract quotes from articles SYNCHRONOUSLY (one at a time).

    This is slower but avoids resource contention issues.
    Use this instead of /quotes/reextract for reliable batch processing.

    Args:
        limit: Number of articles to process (default 50)
        offset: Skip first N articles (use for resuming)
    """
    import time

    articles = get_all_articles_with_text()

    if not articles:
        return {"message": "No articles found", "processed": 0}

    # Apply offset and limit
    to_process = articles[offset:offset + limit]

    results = []
    for i, article in enumerate(to_process):
        article_id = article["id"]
        title = article.get("title", "Untitled")

        try:
            # Delete existing quotes
            deleted = delete_quotes_for_article(article_id)

            # Small delay to avoid rate limits
            time.sleep(0.5)

            # Extract new quotes
            quotes = extract_quotes(
                article.get("clean_text", ""),
                title,
                thorough=True
            )

            if quotes:
                # Generate embeddings
                quotes_with_embeddings = []
                for q in quotes:
                    embedding = generate_embedding(q['quote_text'])
                    quotes_with_embeddings.append({
                        'article_id': article_id,
                        'quote_text': q['quote_text'],
                        'embedding': embedding
                    })
                    time.sleep(0.2)  # Small delay between embeddings

                insert_quotes_batch(quotes_with_embeddings)
                results.append({
                    "id": article_id,
                    "title": title,
                    "status": "success",
                    "quotes_deleted": deleted,
                    "quotes_extracted": len(quotes_with_embeddings)
                })
            else:
                results.append({
                    "id": article_id,
                    "title": title,
                    "status": "no_quotes",
                    "quotes_deleted": deleted,
                    "quotes_extracted": 0
                })

        except Exception as e:
            results.append({
                "id": article_id,
                "title": title,
                "status": "error",
                "error": str(e)
            })

        # Small delay between articles
        time.sleep(0.5)

    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    total_quotes = sum(r.get("quotes_extracted", 0) for r in results)

    return {
        "message": f"Processed {len(to_process)} articles",
        "successful": successful,
        "failed": failed,
        "total_new_quotes": total_quotes,
        "total_articles": len(articles),
        "next_offset": offset + limit if offset + limit < len(articles) else None,
        "results": results
    }


# ============ CATEGORY ENDPOINTS ============

@app.get("/categories", response_model=list[CategoryWithStats])
async def list_categories():
    """Get all categories with matching quote statistics."""
    categories = get_all_categories()

    result = []
    for cat in categories:
        # Get stats if category has an embedding
        if cat.get('embedding'):
            stats = get_category_stats(cat['embedding'])
        else:
            stats = {'matching_quotes_count': 0, 'matching_articles_count': 0}

        result.append(CategoryWithStats(
            id=cat['id'],
            name=cat['name'],
            description=cat.get('description'),
            source=cat.get('source', 'requested'),
            status=cat.get('status', 'pool'),
            last_digest_at=cat.get('last_digest_at'),
            created_at=cat['created_at'],
            matching_quotes_count=stats['matching_quotes_count'],
            matching_articles_count=stats['matching_articles_count']
        ))

    return result


@app.get("/categories/discovered", response_model=list[DiscoveredTheme])
async def get_discovered_themes():
    """
    Get all themes from past digest history.
    These are themes that could be converted into categories.
    """
    themes = get_themes_from_digest_history()

    # Return all themes (sorted by count, most frequent first)
    return [
        DiscoveredTheme(name=t['name'], count=t['count'])
        for t in themes
    ]


@app.post("/categories", response_model=CategoryResponse)
async def create_category(category: CategoryCreate):
    """
    Create a new category.
    Generates an embedding from the name and description for semantic matching.
    New categories start in 'queued' status and will be used in the next daily digest.
    """
    # Generate embedding for semantic matching
    embedding = generate_category_embedding(category.name, category.description)

    category_data = {
        "name": category.name,
        "description": category.description,
        "embedding": embedding,
        "source": "requested",
        "status": "queued"  # New categories get priority in daily digest
    }

    saved = insert_category(category_data)

    if not saved:
        raise HTTPException(status_code=500, detail="Failed to create category")

    return CategoryResponse(
        id=saved['id'],
        name=saved['name'],
        description=saved.get('description'),
        source=saved.get('source', 'requested'),
        status=saved.get('status', 'queued'),
        last_digest_at=saved.get('last_digest_at'),
        created_at=saved['created_at']
    )


@app.get("/categories/{category_id}", response_model=CategoryWithStats)
async def get_category(category_id: str):
    """Get a single category with statistics."""
    cat = get_category_by_id(category_id)

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Get stats if category has an embedding
    if cat.get('embedding'):
        stats = get_category_stats(cat['embedding'])
    else:
        stats = {'matching_quotes_count': 0, 'matching_articles_count': 0}

    return CategoryWithStats(
        id=cat['id'],
        name=cat['name'],
        description=cat.get('description'),
        source=cat.get('source', 'requested'),
        status=cat.get('status', 'pool'),
        last_digest_at=cat.get('last_digest_at'),
        created_at=cat['created_at'],
        matching_quotes_count=stats['matching_quotes_count'],
        matching_articles_count=stats['matching_articles_count']
    )


@app.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category_endpoint(category_id: str, updates: CategoryUpdate):
    """
    Update a category.
    If name or description is changed, regenerates the embedding.
    """
    cat = get_category_by_id(category_id)

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = {}

    # Collect non-None updates
    if updates.name is not None:
        update_data['name'] = updates.name
    if updates.description is not None:
        update_data['description'] = updates.description

    # Regenerate embedding if name or description changed
    if 'name' in update_data or 'description' in update_data:
        new_name = update_data.get('name', cat['name'])
        new_desc = update_data.get('description', cat.get('description'))
        update_data['embedding'] = generate_category_embedding(new_name, new_desc)

    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated = update_category(category_id, update_data)

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update category")

    return CategoryResponse(
        id=updated['id'],
        name=updated['name'],
        description=updated.get('description'),
        source=updated.get('source', 'requested'),
        status=updated.get('status', 'pool'),
        last_digest_at=updated.get('last_digest_at'),
        created_at=updated['created_at']
    )


@app.delete("/categories/{category_id}")
async def delete_category_endpoint(category_id: str):
    """Deactivate a category (soft delete)."""
    cat = get_category_by_id(category_id)

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    success = delete_category(category_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete category")

    return {"message": "Category deactivated", "id": category_id}


@app.get("/categories/{category_id}/preview", response_model=CategoryDigestPreview)
async def preview_category_digest(category_id: str):
    """Preview what a category digest would contain when used in daily digest."""
    cat = get_category_by_id(category_id)

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if not cat.get('embedding'):
        return CategoryDigestPreview(
            category_id=category_id,
            category_name=cat['name'],
            matching_quotes=0,
            matching_articles=0,
            can_send=False,
            sample_quotes=[]
        )

    # Get stats for this category
    stats = get_category_stats(cat['embedding'])

    # Can send if enough quotes from enough articles
    can_send = (
        stats['matching_quotes_count'] >= 3 and
        stats['matching_articles_count'] >= 2
    )

    return CategoryDigestPreview(
        category_id=category_id,
        category_name=cat['name'],
        matching_quotes=stats['matching_quotes_count'],
        matching_articles=stats['matching_articles_count'],
        can_send=can_send,
        sample_quotes=stats['sample_quotes']
    )




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
