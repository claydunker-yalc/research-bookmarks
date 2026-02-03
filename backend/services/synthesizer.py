import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def synthesize_articles(articles: list[dict], focus_topic: str) -> str:
    """
    Synthesize multiple articles into a research brief focused on a specific topic.

    Args:
        articles: List of article dicts with title, clean_text, url, domain
        focus_topic: The specific angle/topic to focus the synthesis on

    Returns:
        Formatted synthesis as markdown
    """
    # Build the articles context
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += f"""
---
SOURCE {i}: {article.get('title', 'Untitled')}
URL: {article.get('url')}
DOMAIN: {article.get('domain')}

{article.get('clean_text', '')}
---
"""

    prompt = f"""You are a research assistant helping synthesize multiple articles into a cohesive research brief.

FOCUS TOPIC: {focus_topic}

Below are {len(articles)} source articles. Synthesize them into a research brief focused specifically on "{focus_topic}".

{articles_text}

Create a research brief with the following structure (use markdown formatting):

## Executive Summary
A 2-3 sentence overview of what these sources collectively say about {focus_topic}.

## Key Insights
Bullet points of the most important findings/ideas related to {focus_topic}. Cite each insight using the article title in parentheses, e.g., ("Article Title").

## Notable Quotes
3-5 direct quotes that are particularly relevant to {focus_topic}. Format as blockquotes with the article title as attribution.

## Points of Agreement
Where do the sources align in their thinking about {focus_topic}?

## Points of Tension
Where do the sources disagree or present different perspectives?

## Questions for Further Research
2-3 questions that emerge from this synthesis that warrant deeper exploration.

## Works Cited
List all sources in MLA format. Use this format for web articles:
Author Last Name, First Name. "Article Title." *Website Name*, Day Month Year published (if available, otherwise use n.d.), URL.

If the author is unknown, start with the article title.

IMPORTANT CITATION RULES:
- Throughout the brief, cite using author last name and shortened title in parentheses, e.g., (Potkalitsky, "Refraction Principle") or (Mollick, "Giving Your AI")
- If no author is apparent, use a shortened title only
- For blockquotes, attribute with author name and full article title
- Be specific about which article each point comes from
- Focus tightly on {focus_topic} - don't try to summarize everything in the articles"""

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text
