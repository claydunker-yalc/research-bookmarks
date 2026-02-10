"""
Category-specific digest generator.

Creates themed email digests for user-defined categories,
finding matching quotes via semantic similarity.
"""

from .category_matcher import find_quotes_for_category


def generate_category_digest(
    category: dict,
    excluded_quote_ids: set[str] | None = None
) -> dict | None:
    """
    Generate a digest email for a specific category.

    Unlike the curator digest which derives themes from clusters,
    category digests use the pre-defined category name as the theme
    and find matching quotes via semantic search.

    Args:
        category: Category dict with name, description, embedding, min_quotes_for_digest
        excluded_quote_ids: Quote IDs to exclude (already used in recent digests)

    Returns:
        dict with 'subject', 'html_body', quote_ids, article_count
        or None if not enough matching quotes found
    """
    embedding = category.get('embedding')
    if not embedding:
        return None

    min_quotes = category.get('min_quotes_for_digest', 5)

    # Find matching quotes
    quotes = find_quotes_for_category(
        category_embedding=embedding,
        similarity_threshold=0.55,
        limit=20,
        excluded_quote_ids=excluded_quote_ids
    )

    if len(quotes) < min_quotes:
        return None

    # Check minimum unique articles (at least 3)
    article_ids = set(q.get('article_id') for q in quotes if q.get('article_id'))
    if len(article_ids) < 3:
        return None

    # Take top quotes for the digest
    selected_quotes = quotes[:min(8, len(quotes))]

    # Build email
    subject = f"Category Digest: {category['name']}"
    html_body = _build_category_email(
        category_name=category['name'],
        category_description=category.get('description'),
        quotes=selected_quotes
    )

    return {
        "subject": subject,
        "html_body": html_body,
        "quote_ids": [q['id'] for q in selected_quotes],
        "article_count": len(set(q.get('article_id') for q in selected_quotes))
    }


def _build_category_email(
    category_name: str,
    category_description: str | None,
    quotes: list[dict]
) -> str:
    """Build the HTML email body for a category digest."""

    quotes_html = ""
    for q in quotes:
        quotes_html += f"""
        <div class="quote">
            <p>"{q.get('quote_text', '')}"</p>
            <cite>— <a href="{q.get('article_url', '#')}">{q.get('article_title', 'Untitled')}</a></cite>
        </div>
        """

    description_html = ""
    if category_description:
        description_html = f'<p class="description">{category_description}</p>'

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            line-height: 1.7;
            color: #2d2d2d;
            max-width: 600px;
            margin: 0 auto;
            padding: 24px;
            background: #fafafa;
        }}
        .header {{
            border-bottom: 2px solid #10b981;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #10b981;
            margin: 0;
            font-weight: 500;
        }}
        .category-name {{
            font-size: 24px;
            color: #1a1a1a;
            margin: 8px 0 0 0;
            font-style: italic;
        }}
        .description {{
            font-size: 14px;
            color: #666;
            margin-top: 8px;
            font-style: normal;
        }}
        .quote {{
            padding: 16px 20px;
            border-left: 3px solid #10b981;
            margin: 20px 0;
            background: #f0fdf4;
            border-radius: 0 8px 8px 0;
        }}
        .quote p {{
            font-size: 16px;
            font-style: italic;
            margin: 0 0 10px 0;
            color: #1a1a1a;
        }}
        .quote cite {{
            font-size: 13px;
            color: #555;
            font-style: normal;
        }}
        .quote cite a {{
            color: #059669;
            text-decoration: none;
        }}
        .quote cite a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Category Digest</h1>
        <p class="category-name">{category_name}</p>
        {description_html}
    </div>

    <p style="color: #666; font-size: 14px;">
        Here are quotes from your library that match this category:
    </p>

    {quotes_html}

    <div class="footer">
        <p>Category Digest from Research Bookmarks</p>
    </div>
</body>
</html>
"""
