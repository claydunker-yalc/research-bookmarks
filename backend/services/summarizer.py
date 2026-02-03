import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_summary(text: str, title: str | None = None) -> str:
    """
    Generate a 1-2 sentence summary of the article using Claude Haiku.

    Args:
        text: The article text to summarize
        title: Optional article title for context

    Returns:
        A concise 1-2 sentence summary
    """
    max_chars = 8000
    truncated_text = text[:max_chars] if len(text) > max_chars else text

    context = f"Title: {title}\n\n" if title else ""

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"""Summarize this article in 1-2 sentences. Be concise and capture the main point.

{context}Article:
{truncated_text}

Summary:"""
            }
        ]
    )

    return message.content[0].text.strip()
