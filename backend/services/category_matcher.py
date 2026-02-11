"""
Category-based quote matching service.

Uses semantic similarity to find quotes that match a category's
name/description embedding.
"""

from .embeddings import generate_embedding
from database import search_quotes_by_embedding, get_all_quotes_with_articles


def generate_category_embedding(name: str, description: str | None = None) -> list[float]:
    """
    Generate an embedding for a category based on its name and description.

    Args:
        name: The category name (e.g., "AI Ethics")
        description: Optional description of what topics this category covers

    Returns:
        1536-dimensional embedding vector
    """
    # Combine name and description for richer semantic matching
    if description:
        text = f"{name}: {description}"
    else:
        text = name

    return generate_embedding(text)


def find_quotes_for_category(
    category_embedding: list[float],
    similarity_threshold: float = 0.35,
    limit: int = 50,
    excluded_quote_ids: set[str] | None = None
) -> list[dict]:
    """
    Find quotes that semantically match a category.

    Uses embedding similarity to find quotes related to the category's theme.
    Lower threshold than quote-to-quote clustering since we're matching
    quotes to an abstract concept.

    Args:
        category_embedding: The category's embedding vector
        similarity_threshold: Minimum similarity score (default 0.35)
        limit: Maximum quotes to return
        excluded_quote_ids: Quote IDs to exclude (already used in recent digests)

    Returns:
        List of matching quotes with article metadata, sorted by similarity
    """
    # Search quotes by embedding
    matching_quotes = search_quotes_by_embedding(
        category_embedding,
        limit=limit * 2,  # Fetch extra to account for exclusions
        threshold=similarity_threshold
    )

    if not matching_quotes:
        return []

    # Get full quote data with article info
    all_quotes = get_all_quotes_with_articles()
    quotes_map = {q['id']: q for q in all_quotes}

    # Enrich matches with article metadata
    enriched = []
    for match in matching_quotes:
        quote_id = match['id']

        # Skip excluded quotes
        if excluded_quote_ids and quote_id in excluded_quote_ids:
            continue

        full_quote = quotes_map.get(quote_id)
        if full_quote:
            enriched.append({
                **full_quote,
                'similarity': match['similarity']
            })

    # Sort by similarity descending
    enriched.sort(key=lambda x: x.get('similarity', 0), reverse=True)

    return enriched[:limit]


def get_category_stats(category_embedding: list[float], excluded_quote_ids: set[str] | None = None) -> dict:
    """
    Get statistics for a category's matching quotes.

    Args:
        category_embedding: The category's embedding vector
        excluded_quote_ids: Quote IDs to exclude

    Returns:
        Dict with matching_quotes_count, matching_articles_count, sample_quotes
    """
    quotes = find_quotes_for_category(
        category_embedding,
        similarity_threshold=0.35,
        limit=100,
        excluded_quote_ids=excluded_quote_ids
    )

    # Count unique articles
    article_ids = set(q.get('article_id') for q in quotes if q.get('article_id'))

    # Get top 3 sample quotes
    sample_quotes = []
    for q in quotes[:3]:
        sample_quotes.append({
            'quote_text': q.get('quote_text'),
            'article_title': q.get('article_title'),
            'article_url': q.get('article_url'),
            'similarity': q.get('similarity')
        })

    return {
        'matching_quotes_count': len(quotes),
        'matching_articles_count': len(article_ids),
        'sample_quotes': sample_quotes
    }
