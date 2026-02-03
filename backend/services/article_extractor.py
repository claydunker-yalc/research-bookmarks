from urllib.parse import urlparse
import re
import httpx
from newspaper import Article, ArticleException


class ExtractionError(Exception):
    """Raised when article extraction fails."""
    pass


def sanitize_html(html: str) -> str:
    """Remove control characters and NULL bytes that break XML parsing."""
    # Remove NULL bytes
    html = html.replace('\x00', '')
    # Remove other control characters except tab, newline, carriage return
    html = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', html)
    return html


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Upgrade-Insecure-Requests': '1',
}


def is_medium_url(url: str) -> bool:
    """Check if URL is a Medium article."""
    parsed = urlparse(url)
    return 'medium.com' in parsed.netloc or parsed.netloc.endswith('.medium.com')


def get_medium_proxy_url(url: str) -> str:
    """Convert Medium URL to use scribe.rip proxy."""
    return url.replace('medium.com', 'scribe.rip')


def fetch_html(url: str) -> str:
    """Fetch HTML content from URL with retry logic."""
    with httpx.Client(http2=True, follow_redirects=True, timeout=20) as client:
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text


def extract_article(url: str) -> dict:
    """
    Extract clean article content from a URL.

    Returns:
        dict with keys: title, clean_text, domain

    Raises:
        ExtractionError: If extraction fails
    """
    original_url = url
    original_domain = urlparse(url).netloc.replace("www.", "")

    try:
        # Try fetching the URL directly first
        try:
            html = fetch_html(url)
        except httpx.HTTPStatusError as e:
            # If Medium returns 403, try the proxy
            if is_medium_url(url) and e.response.status_code == 403:
                proxy_url = get_medium_proxy_url(url)
                html = fetch_html(proxy_url)
            else:
                raise

        # Sanitize HTML to remove control characters
        html = sanitize_html(html)

        article = Article(original_url)
        article.set_html(html)
        article.parse()

        title = article.title
        clean_text = article.text

        if not clean_text or len(clean_text.strip()) < 100:
            raise ExtractionError(
                "Could not extract sufficient article content. "
                "The page may be paywalled, require JavaScript, or not contain article text."
            )

        return {
            "title": title,
            "clean_text": clean_text,
            "domain": original_domain
        }

    except httpx.HTTPStatusError as e:
        raise ExtractionError(f"Failed to fetch article: {e.response.status_code} error")
    except httpx.RequestError as e:
        raise ExtractionError(f"Failed to connect: {str(e)}")
    except ArticleException as e:
        raise ExtractionError(f"Failed to parse article: {str(e)}")
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Unexpected error: {str(e)}")
