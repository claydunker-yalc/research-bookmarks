"""
Quote-first digest generator.

Creates "curator's pick" emails that surface thematic connections
across your reading, starting with quotes and deriving themes from them.
"""

import anthropic
from config import ANTHROPIC_API_KEY
from .quote_clusterer import get_cluster_for_digest

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_curator_digest(quotes_with_articles: list[dict], relaxed: bool = True) -> dict | None:
    """
    Generate a curator's pick email from quote clusters.

    Args:
        quotes_with_articles: All quotes with article metadata
        relaxed: If True, don't require 2+ month old anchor (for new libraries)

    Returns:
        dict with 'subject' and 'html_body', or None if no good cluster
    """
    # Find the best quote cluster
    cluster = get_cluster_for_digest(quotes_with_articles, relaxed=relaxed)

    if not cluster:
        return None

    anchor = cluster['anchor_quote']
    recent = cluster['recent_quotes']

    # Build context for Claude to derive the theme
    quotes_context = f"""ANCHOR QUOTE (from 2+ months ago):
"{anchor['quote_text']}"
— Article: "{anchor.get('article_title', 'Untitled')}"
   Domain: {anchor.get('article_domain', 'Unknown')}

RECENT QUOTES (last 30 days):
"""
    for i, q in enumerate(recent, 1):
        quotes_context += f"""
{i}. "{q['quote_text']}"
   — Article: "{q.get('article_title', 'Untitled')}"
   Domain: {q.get('article_domain', 'Unknown')}
"""

    prompt = f"""You're a research curator who noticed a thematic connection across someone's bookmarked articles. These quotes cluster together semantically - your job is to name the SPECIFIC theme and craft a brief, insightful email.

{quotes_context}

Your task:
1. Derive a GRANULAR theme from these quotes (e.g., "assessment authenticity" NOT "AI in education")
2. Identify what tension, question, or insight emerges when these quotes talk to each other
3. Write a curator's pick email

Rules:
- Theme should be 2-4 words, specific and evocative
- Don't summarize - let the quotes speak
- One sentence max about what they raise together
- Tone: thoughtful colleague, not corporate newsletter

Output in this EXACT format:

THEME: [2-4 word granular theme]
AUTHOR: [Last name of anchor quote's author, or "Unknown" if not apparent]
SUBJECT: Worth revisiting: [Author] on [theme]

ANCHOR_QUOTE: [The exact anchor quote text - copy verbatim]
ANCHOR_SOURCE: [Article title]

RECENT_1_QUOTE: [First recent quote - copy verbatim]
RECENT_1_SOURCE: [Article title]

RECENT_2_QUOTE: [Second recent quote - copy verbatim]
RECENT_2_SOURCE: [Article title]

RECENT_3_QUOTE: [Third recent quote if available - copy verbatim, or "NONE"]
RECENT_3_SOURCE: [Article title, or "NONE"]

TENSION: [One sentence about what question or tension these quotes raise together]"""

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        response = message.content[0].text.strip()
        return _parse_curator_response(response, anchor, recent)

    except Exception as e:
        print(f"Digest generation failed: {e}")
        return None


def _parse_curator_response(response: str, anchor: dict, recent: list[dict]) -> dict:
    """Parse Claude's response into email components."""

    def extract_field(text: str, field: str) -> str:
        """Extract a field value from the response."""
        lines = text.split('\n')
        for line in lines:
            if line.startswith(f"{field}:"):
                return line.split(":", 1)[1].strip()
        return ""

    theme = extract_field(response, "THEME") or "emerging patterns"
    author = extract_field(response, "AUTHOR") or "your reading"
    subject = extract_field(response, "SUBJECT") or f"Worth revisiting: {author} on {theme}"
    tension = extract_field(response, "TENSION") or "These quotes surface an interesting tension in your recent reading."

    # Use parsed quotes or fall back to originals
    anchor_quote = extract_field(response, "ANCHOR_QUOTE") or anchor['quote_text']
    anchor_source = extract_field(response, "ANCHOR_SOURCE") or anchor.get('article_title', 'Untitled')

    recent_quotes = []
    for i in range(1, 4):
        quote = extract_field(response, f"RECENT_{i}_QUOTE")
        source = extract_field(response, f"RECENT_{i}_SOURCE")
        if quote and quote != "NONE" and i <= len(recent):
            recent_quotes.append({
                'quote': quote,
                'source': source or recent[i-1].get('article_title', 'Untitled'),
                'url': recent[i-1].get('article_url', '#')
            })

    # Fall back to original recent quotes if parsing failed
    if not recent_quotes:
        recent_quotes = [
            {
                'quote': q['quote_text'],
                'source': q.get('article_title', 'Untitled'),
                'url': q.get('article_url', '#')
            }
            for q in recent[:3]
        ]

    # Build HTML email
    html_body = _build_curator_email(
        theme=theme,
        anchor_quote=anchor_quote,
        anchor_source=anchor_source,
        anchor_url=anchor.get('article_url', '#'),
        recent_quotes=recent_quotes,
        tension=tension
    )

    return {
        "subject": subject,
        "html_body": html_body,
        "theme": theme,
        "anchor_article": anchor_source,
        "recent_count": len(recent_quotes)
    }


def _build_curator_email(
    theme: str,
    anchor_quote: str,
    anchor_source: str,
    anchor_url: str,
    recent_quotes: list[dict],
    tension: str
) -> str:
    """Build the HTML email body."""

    recent_html = ""
    for rq in recent_quotes:
        recent_html += f"""
        <div class="quote recent-quote">
            <p>"{rq['quote']}"</p>
            <cite>— <a href="{rq['url']}">{rq['source']}</a></cite>
        </div>
        """

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
            border-bottom: 2px solid #667eea;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #667eea;
            margin: 0;
            font-weight: 500;
        }}
        .theme {{
            font-size: 24px;
            color: #1a1a1a;
            margin: 8px 0 0 0;
            font-style: italic;
        }}
        .anchor-quote {{
            background: #f0efff;
            border-left: 4px solid #667eea;
            padding: 20px 24px;
            margin: 24px 0;
            border-radius: 0 8px 8px 0;
        }}
        .anchor-quote p {{
            font-size: 18px;
            font-style: italic;
            margin: 0 0 12px 0;
            color: #1a1a1a;
        }}
        .anchor-quote cite {{
            font-size: 14px;
            color: #555;
            font-style: normal;
        }}
        .anchor-quote cite a {{
            color: #667eea;
            text-decoration: none;
        }}
        .section-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #888;
            margin: 32px 0 16px 0;
        }}
        .recent-quote {{
            padding: 16px 0;
            border-bottom: 1px solid #eee;
        }}
        .recent-quote:last-child {{
            border-bottom: none;
        }}
        .recent-quote p {{
            font-size: 16px;
            margin: 0 0 8px 0;
            color: #333;
        }}
        .recent-quote cite {{
            font-size: 13px;
            color: #666;
            font-style: normal;
        }}
        .recent-quote cite a {{
            color: #667eea;
            text-decoration: none;
        }}
        .tension {{
            background: #1a1a2e;
            color: #fff;
            padding: 20px 24px;
            border-radius: 8px;
            margin: 32px 0;
            font-size: 15px;
            line-height: 1.6;
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
        <h1>Curator's Pick</h1>
        <p class="theme">{theme}</p>
    </div>

    <div class="anchor-quote">
        <p>"{anchor_quote}"</p>
        <cite>— <a href="{anchor_url}">{anchor_source}</a></cite>
    </div>

    <p class="section-label">Your recent reading picks up this thread</p>

    {recent_html}

    <div class="tension">
        {tension}
    </div>

    <div class="footer">
        <p>Curator's Pick from Research Bookmarks</p>
    </div>
</body>
</html>
"""


# Keep the old function for backwards compatibility but mark deprecated
def generate_digest(recent_articles: list[dict], rediscovery_articles: list[dict]) -> dict:
    """
    DEPRECATED: Use generate_curator_digest instead.
    This is the old summary-based digest generator.
    """
    # ... keeping for backwards compat but won't be called
    return None
