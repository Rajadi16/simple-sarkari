"""
Source registry model — defines monitored government websites.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from lib.dates import utcnow


class Source(BaseModel):
    """A government website source configuration."""
    id: str = Field(..., description="Unique source identifier, e.g. 'pib'")
    name: str = Field(..., description="Human-readable name")
    base_domains: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)
    adapter: str = Field(..., description="Crawler adapter class name, e.g. 'pib'")
    government_level: str = Field(..., description="'central' or 'state'")
    state: str | None = None
    allowed_content_types: list[str] = Field(default_factory=list)
    enabled: bool = True

    # Crawl behaviour
    crawl_interval_minutes: int = 360
    request_delay_seconds: int = 5
    max_pages_per_run: int = 10
    max_documents_per_run: int = 100
    respect_robots: bool = True
    stop_on_403: bool = True
    stop_on_429: bool = True

    # Metadata
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CrawlRunRequest(BaseModel):
    """Body for POST /api/admin/sources/{source_id}/crawl."""
    max_pages: int = 10
    max_documents: int = 50
    backfill: bool = False


class CrawlRun(BaseModel):
    """Result of a single crawler run."""
    id: str = Field(default="")
    source_id: str
    status: str = "pending"  # pending | running | completed | failed
    pages_fetched: int = 0
    documents_discovered: int = 0
    documents_new: int = 0
    documents_duplicate: int = 0
    blocked_requests: int = 0
    errors: list[dict] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
