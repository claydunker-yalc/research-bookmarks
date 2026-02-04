from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def check_url_exists(url: str) -> dict | None:
    """Check if a URL already exists in the database. Returns the article if found."""
    result = supabase.table("articles").select("*").eq("url", url).execute()
    if result.data:
        return result.data[0]
    return None


def insert_article(article_data: dict) -> dict:
    """Insert a new article into the database."""
    result = supabase.table("articles").insert(article_data).execute()
    return result.data[0]


def get_all_articles(limit: int = 50, offset: int = 0) -> list[dict]:
    """Get all articles, ordered by creation date (newest first)."""
    result = (
        supabase.table("articles")
        .select("id, url, title, summary, domain, created_at")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


def get_article_by_id(article_id: str) -> dict | None:
    """Get a single article by ID."""
    result = supabase.table("articles").select("*").eq("id", article_id).execute()
    if result.data:
        return result.data[0]
    return None


def search_by_embedding(query_embedding: list[float], limit: int = 10) -> list[dict]:
    """Search articles by semantic similarity using vector search."""
    result = supabase.rpc(
        "search_articles",
        {"query_embedding": query_embedding, "match_count": limit}
    ).execute()
    return result.data


def get_articles_by_ids(article_ids: list[str]) -> list[dict]:
    """Get multiple articles by their IDs, including full text."""
    result = (
        supabase.table("articles")
        .select("id, url, title, clean_text, summary, domain, created_at")
        .in_("id", article_ids)
        .execute()
    )
    return result.data


def get_recent_articles(days: int = 3) -> list[dict]:
    """Get articles added in the last N days."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = (
        supabase.table("articles")
        .select("id, url, title, summary, domain, created_at")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_random_older_articles(count: int = 3, exclude_days: int = 3) -> list[dict]:
    """Get random articles older than N days for rediscovery."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=exclude_days)).isoformat()

    # Get older articles
    result = (
        supabase.table("articles")
        .select("id, url, title, summary, domain, created_at")
        .lt("created_at", cutoff)
        .execute()
    )

    articles = result.data
    if not articles:
        return []

    # Randomly select up to 'count' articles
    import random
    return random.sample(articles, min(count, len(articles)))


def get_article_count() -> int:
    """Get total number of articles."""
    result = supabase.table("articles").select("id", count="exact").execute()
    return result.count or 0


# Quote-related functions

def insert_quote(quote_data: dict) -> dict:
    """Insert a new quote into the database."""
    result = supabase.table("quotes").insert(quote_data).execute()
    return result.data[0] if result.data else None


def insert_quotes_batch(quotes: list[dict]) -> list[dict]:
    """Insert multiple quotes at once."""
    if not quotes:
        return []
    result = supabase.table("quotes").insert(quotes).execute()
    return result.data


def get_quotes_for_article(article_id: str) -> list[dict]:
    """Get all quotes for a specific article."""
    result = (
        supabase.table("quotes")
        .select("*")
        .eq("article_id", article_id)
        .execute()
    )
    return result.data


def get_all_quotes_with_articles() -> list[dict]:
    """
    Get all quotes with their article metadata.
    Returns quotes joined with article info for clustering.
    """
    # Get all quotes
    quotes_result = supabase.table("quotes").select("*").execute()
    quotes = quotes_result.data

    if not quotes:
        return []

    # Get unique article IDs
    article_ids = list(set(q['article_id'] for q in quotes))

    # Get article metadata
    articles_result = (
        supabase.table("articles")
        .select("id, url, title, domain, created_at")
        .in_("id", article_ids)
        .execute()
    )
    articles_map = {a['id']: a for a in articles_result.data}

    # Merge quote and article data
    enriched_quotes = []
    for q in quotes:
        article = articles_map.get(q['article_id'], {})
        enriched_quotes.append({
            **q,
            'article_title': article.get('title'),
            'article_url': article.get('url'),
            'article_domain': article.get('domain'),
            'article_created_at': article.get('created_at')
        })

    return enriched_quotes


def get_quote_count() -> int:
    """Get total number of quotes."""
    result = supabase.table("quotes").select("id", count="exact").execute()
    return result.count or 0


def article_has_quotes(article_id: str) -> bool:
    """Check if an article already has quotes extracted."""
    result = (
        supabase.table("quotes")
        .select("id", count="exact")
        .eq("article_id", article_id)
        .execute()
    )
    return (result.count or 0) > 0


def get_articles_without_quotes() -> list[dict]:
    """Get articles that don't have quotes extracted yet."""
    # Get all article IDs that have quotes
    quotes_result = supabase.table("quotes").select("article_id").execute()
    articles_with_quotes = set(q['article_id'] for q in quotes_result.data)

    # Get all articles
    articles_result = (
        supabase.table("articles")
        .select("id, url, title, clean_text, domain, created_at")
        .execute()
    )

    # Filter to those without quotes
    return [a for a in articles_result.data if a['id'] not in articles_with_quotes]


# Digest history functions

def get_recent_digest_anchor_ids(days: int = 7) -> set[str]:
    """Get anchor quote IDs used in recent digests to avoid repetition."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        result = (
            supabase.table("digest_history")
            .select("anchor_quote_id")
            .gte("sent_at", cutoff)
            .execute()
        )
        return set(r['anchor_quote_id'] for r in result.data if r.get('anchor_quote_id'))
    except Exception:
        # Table might not exist yet
        return set()


def save_digest_history(theme: str, anchor_quote_id: str, anchor_article_id: str, cluster_quote_ids: list[str]) -> dict | None:
    """Record a sent digest to avoid repetition."""
    try:
        result = supabase.table("digest_history").insert({
            "theme": theme,
            "anchor_quote_id": anchor_quote_id,
            "anchor_article_id": anchor_article_id,
            "cluster_quote_ids": cluster_quote_ids
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Failed to save digest history: {e}")
        return None


def delete_quotes_for_article(article_id: str) -> int:
    """Delete all quotes for an article (for re-extraction)."""
    try:
        result = supabase.table("quotes").delete().eq("article_id", article_id).execute()
        return len(result.data) if result.data else 0
    except Exception as e:
        print(f"Failed to delete quotes: {e}")
        return 0


def get_all_articles_with_text() -> list[dict]:
    """Get all articles with their full text for re-extraction."""
    result = (
        supabase.table("articles")
        .select("id, url, title, clean_text, domain, created_at")
        .execute()
    )
    return result.data
