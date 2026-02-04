"""
Quote clustering service.

Clusters quotes by semantic similarity to find thematic connections
across articles. Uses a simple greedy clustering approach.
"""

from datetime import datetime, timedelta
import numpy as np


def parse_embedding(emb) -> np.ndarray:
    """Parse embedding from various formats (list, string, etc.)."""
    if emb is None:
        return None
    if isinstance(emb, np.ndarray):
        return emb
    if isinstance(emb, list):
        return np.array(emb, dtype=np.float32)
    if isinstance(emb, str):
        # Handle Supabase's string format: "[0.1, 0.2, ...]"
        import json
        try:
            return np.array(json.loads(emb), dtype=np.float32)
        except:
            return None
    return None


def cosine_similarity(a, b) -> float:
    """Calculate cosine similarity between two vectors."""
    a = parse_embedding(a)
    b = parse_embedding(b)
    if a is None or b is None:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_quote_clusters(
    quotes: list[dict],
    similarity_threshold: float = 0.60,
    min_quotes: int = 5,
    min_articles: int = 3,
    require_old_anchor: bool = True
) -> list[dict]:
    """
    Find clusters of semantically similar quotes.

    Args:
        quotes: List of quote dicts with 'id', 'article_id', 'quote_text',
                'embedding', 'created_at', and article metadata
        similarity_threshold: Minimum cosine similarity to be in same cluster
        min_quotes: Minimum quotes needed for a valid cluster
        min_articles: Minimum unique articles needed for a valid cluster
        require_old_anchor: If True, requires a 2+ month old quote as anchor

    Returns:
        List of cluster dicts, each containing:
        - quotes: list of quotes in the cluster
        - article_ids: set of unique article IDs
        - has_old_anchor: whether cluster has a 2+ month old quote
        - anchor_quote: the oldest high-quality quote (if old enough)
        - recent_quotes: quotes from last 30 days
    """
    if not quotes or len(quotes) < min_quotes:
        return []

    # Filter quotes that have embeddings
    quotes_with_embeddings = [q for q in quotes if q.get('embedding')]
    if len(quotes_with_embeddings) < min_quotes:
        return []

    # Track which quotes have been clustered
    clustered = set()
    clusters = []

    # Sort by created_at so older quotes anchor clusters
    sorted_quotes = sorted(quotes_with_embeddings, key=lambda q: q['created_at'])

    for anchor in sorted_quotes:
        if anchor['id'] in clustered:
            continue

        # Start a new cluster with this anchor
        cluster_quotes = [anchor]
        clustered.add(anchor['id'])

        # Find similar quotes
        for candidate in sorted_quotes:
            if candidate['id'] in clustered:
                continue

            sim = cosine_similarity(anchor['embedding'], candidate['embedding'])
            if sim >= similarity_threshold:
                cluster_quotes.append(candidate)
                clustered.add(candidate['id'])

        # Check if cluster meets criteria
        article_ids = set(q['article_id'] for q in cluster_quotes)

        if len(cluster_quotes) >= min_quotes and len(article_ids) >= min_articles:
            # Determine old vs recent quotes
            two_months_ago = datetime.utcnow() - timedelta(days=60)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            old_quotes = []
            recent_quotes = []

            for q in cluster_quotes:
                # Handle both string and datetime
                created = q['created_at']
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created = created.replace(tzinfo=None)

                if created < two_months_ago:
                    old_quotes.append(q)
                else:
                    recent_quotes.append(q)

            # Check anchor requirements
            has_old_anchor = len(old_quotes) > 0

            if require_old_anchor:
                # Strict mode: need old anchor + recent quotes
                if has_old_anchor and len(recent_quotes) >= 2:
                    clusters.append({
                        'quotes': cluster_quotes,
                        'article_ids': article_ids,
                        'has_old_anchor': True,
                        'anchor_quote': old_quotes[0],
                        'recent_quotes': recent_quotes[:3],
                        'total_quotes': len(cluster_quotes),
                        'total_articles': len(article_ids)
                    })
            else:
                # Relaxed mode: use oldest quote as anchor, rest as recent
                # Good for testing or when library is new
                clusters.append({
                    'quotes': cluster_quotes,
                    'article_ids': article_ids,
                    'has_old_anchor': has_old_anchor,
                    'anchor_quote': cluster_quotes[0],  # Oldest in cluster
                    'recent_quotes': cluster_quotes[1:4],  # Next 3 as "recent"
                    'total_quotes': len(cluster_quotes),
                    'total_articles': len(article_ids)
                })

    # Sort clusters by total quotes (most developed themes first)
    clusters.sort(key=lambda c: c['total_quotes'], reverse=True)

    return clusters


def get_cluster_for_digest(quotes: list[dict], relaxed: bool = False, excluded_anchor_ids: set[str] = None) -> dict | None:
    """
    Get a cluster for today's digest email, avoiding recently used anchors.

    Args:
        quotes: List of quote dicts with embeddings and article metadata
        relaxed: If True, don't require 2+ month old anchor (for testing new libraries)
        excluded_anchor_ids: Set of quote IDs to exclude as anchors (recently used)

    Returns a suitable cluster, rotating through options to provide variety.
    """
    import random

    clusters = find_quote_clusters(quotes, require_old_anchor=not relaxed)

    if not clusters:
        return None

    excluded_anchor_ids = excluded_anchor_ids or set()

    # Filter out clusters whose anchors were recently used
    available_clusters = [
        c for c in clusters
        if c['anchor_quote']['id'] not in excluded_anchor_ids
    ]

    # If all clusters were recently used, reset and allow any
    if not available_clusters:
        available_clusters = clusters

    # Pick randomly from the top clusters (weighted toward better ones)
    # Take top 3 clusters and pick one randomly
    top_clusters = available_clusters[:min(3, len(available_clusters))]

    # Weight toward the first (best) cluster but allow variety
    weights = [3, 2, 1][:len(top_clusters)]
    selected = random.choices(top_clusters, weights=weights, k=1)[0]

    return selected
