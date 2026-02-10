from datetime import datetime
from pydantic import BaseModel, HttpUrl


class ArticleCreate(BaseModel):
    url: HttpUrl


class ArticleManualCreate(BaseModel):
    url: HttpUrl
    title: str
    content: str


class ArticleResponse(BaseModel):
    id: str
    url: str
    title: str | None
    summary: str | None
    domain: str | None
    created_at: datetime


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResult(BaseModel):
    id: str
    url: str
    title: str | None
    summary: str | None
    domain: str | None
    created_at: datetime
    similarity: float


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class SynthesizeRequest(BaseModel):
    article_ids: list[str]
    focus_topic: str


class SynthesisResponse(BaseModel):
    focus_topic: str
    summary: str
    sources: list[dict]


class ArticleExport(BaseModel):
    """Full article data for export to NotebookLM and similar tools."""
    id: str
    url: str
    title: str | None
    summary: str | None
    clean_text: str | None
    domain: str | None
    created_at: datetime


# Category models

class CategoryCreate(BaseModel):
    name: str
    description: str | None = None
    digest_frequency: str = "weekly"  # 'weekly' or 'manual'
    min_quotes_for_digest: int = 5


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    digest_frequency: str | None = None
    min_quotes_for_digest: int | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    description: str | None
    source: str  # 'discovered' or 'requested'
    is_active: bool
    digest_frequency: str
    min_quotes_for_digest: int
    last_digest_at: datetime | None
    created_at: datetime


class CategoryWithStats(CategoryResponse):
    """Category with matching quote statistics."""
    matching_quotes_count: int
    matching_articles_count: int


class CategoryDigestPreview(BaseModel):
    """Preview of what a category digest would contain."""
    category_id: str
    category_name: str
    matching_quotes: int
    matching_articles: int
    can_send: bool  # True if meets minimum requirements
    sample_quotes: list[dict]  # First 3 matching quotes


class DiscoveredTheme(BaseModel):
    """A theme discovered from past digest history."""
    name: str
    count: int  # Number of times this theme appeared
