from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimensional embedding for the given text using OpenAI's text-embedding-3-small.

    Args:
        text: The text to embed (article content or search query)

    Returns:
        List of 1536 floats representing the embedding vector
    """
    max_chars = 8000
    truncated_text = text[:max_chars] if len(text) > max_chars else text

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=truncated_text
    )

    return response.data[0].embedding
