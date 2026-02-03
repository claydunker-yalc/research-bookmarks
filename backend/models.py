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
