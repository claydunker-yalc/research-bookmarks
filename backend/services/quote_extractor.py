import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def extract_quotes(article_text: str, article_title: str, author: str = None, thorough: bool = True) -> list[dict]:
    """
    Extract notable, quotable passages from an article.

    Args:
        article_text: The full article text
        article_title: Title of the article
        author: Author name if known
        thorough: If True, extract 5-10 quotes covering different themes.
                  If False, extract 3-5 quotes (legacy behavior).

    Returns:
        List of dicts with 'quote_text' key
    """
    if not article_text or len(article_text) < 200:
        return []

    # Truncate very long articles to avoid token limits
    max_chars = 20000 if thorough else 15000
    text = article_text[:max_chars] if len(article_text) > max_chars else article_text

    if thorough:
        prompt = f"""Extract 5-10 notable quotes from this article, ensuring THEMATIC DIVERSITY.

ARTICLE TITLE: {article_title}
{f'AUTHOR: {author}' if author else ''}

ARTICLE TEXT:
{text}

IMPORTANT: Many articles touch on MULTIPLE themes or topics. Extract quotes that represent DIFFERENT ideas, not just variations of the same point.

For example, an article about "AI in education" might touch on:
- Assessment/grading concerns
- Student agency and learning
- Teacher roles and workload
- Epistemology and knowledge
- Institutional change
- Ethics and equity

Extract quotes covering AS MANY different themes as the article touches on.

Look for:
- Strong claims or provocative statements
- Memorable insights that stand alone
- Key arguments from different sections
- Surprising or counterintuitive observations
- Quotes that would connect to DIFFERENT conversations

Each quote should be:
- 2-4 sentences (complete thoughts, not fragments)
- Exact text from the article (don't paraphrase)
- Able to stand alone without context
- Representing a DISTINCT idea from other quotes you extract

Return ONLY a JSON array of objects, each with "quote_text" field.
Example format:
[
  {{"quote_text": "Quote about one theme..."}},
  {{"quote_text": "Quote about a different theme..."}},
  {{"quote_text": "Quote about yet another angle..."}}
]

JSON array:"""
        max_quotes = 10
    else:
        prompt = f"""Extract 3-5 notable quotes from this article that would be worth revisiting later.

ARTICLE TITLE: {article_title}
{f'AUTHOR: {author}' if author else ''}

ARTICLE TEXT:
{text}

Look for passages that are:
- Strong claims or provocative statements
- Memorable, well-crafted insights that stand alone
- Key arguments that capture the article's essence
- Surprising or counterintuitive observations

Each quote should be:
- 2-4 sentences (complete thoughts, not fragments)
- Exact text from the article (don't paraphrase)
- Able to stand alone without context

Return ONLY a JSON array of objects, each with a "quote_text" field.
Example format:
[
  {{"quote_text": "The exact quote from the article goes here. It might span multiple sentences."}},
  {{"quote_text": "Another notable quote that stands alone as an insight."}}
]

If the article doesn't have good quotable passages, return an empty array: []

JSON array:"""
        max_quotes = 5

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=3000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()

        # Parse JSON response
        import json

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        quotes = json.loads(response_text)

        # Validate structure
        if not isinstance(quotes, list):
            return []

        valid_quotes = []
        for q in quotes:
            if isinstance(q, dict) and "quote_text" in q and len(q["quote_text"]) > 50:
                valid_quotes.append({"quote_text": q["quote_text"].strip()})

        return valid_quotes[:max_quotes]

    except Exception as e:
        print(f"Quote extraction failed: {e}")
        return []


def extract_author_from_text(article_text: str, domain: str) -> str | None:
    """
    Try to extract author name from article text.
    Uses simple heuristics - not always accurate.
    """
    import re

    # Common patterns
    patterns = [
        r"^By\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",  # "By John Smith"
        r"Written by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"Author:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    ]

    first_500 = article_text[:500]

    for pattern in patterns:
        match = re.search(pattern, first_500, re.MULTILINE)
        if match:
            return match.group(1)

    return None
