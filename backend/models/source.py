"""
Source registry model — defines monitored government websites.

Person 1 (Aditya) — Ingestion & Source Verification
"""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from lib.dates import utcnow


class CrawlPolicy(BaseModel):
    """Crawl behaviour settings, nested inside Source."""
    max_pages_per_run: int = 10
    request_delay_seconds: int = 5
    max_documents_per_run: int = 50
    respect_robots: bool = True
    stop_on_403: bool = True
    stop_on_429: bool = True


class Source(BaseModel):
    """
    A government website source configuration.

    `source_id` is the canonical identifier used throughout the pipeline
    (e.g. "pib", "karnataka_egazette").
    """
    source_id: str = Field(..., description="Unique source identifier, e.g. 'pib'")
    name: str = Field(..., description="Human-readable name")
    base_domains: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)
    adapter: str = Field(..., description="Crawler adapter key, e.g. 'pib'")
    government_level: str = Field(..., description="'central' or 'state'")
    state: str | None = None
    allowed_document_types: list[str] = Field(
        default_factory=list,
        description="e.g. ['press_release', 'circular', 'notification']",
    )
    allowed_path_patterns: list[str] = Field(
        default_factory=list,
        description="URL path prefixes/patterns this adapter may follow",
    )
    crawl_policy: CrawlPolicy = Field(default_factory=CrawlPolicy)
    status: str = Field(default="active", description="'active' | 'paused' | 'disabled'")

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_crawler_config(self) -> dict:
        """
        Flatten the Source into the dict shape that BaseCrawlerAdapter expects.
        Keeps backward-compatibility with adapter code that reads source_config keys directly.
        """
        return {
            "source_id": self.source_id,
            "name": self.name,
            "base_domains": self.base_domains,
            "seed_urls": self.seed_urls,
            "adapter": self.adapter,
            "government_level": self.government_level,
            "state": self.state,
            "allowed_document_types": self.allowed_document_types,
            "allowed_path_patterns": self.allowed_path_patterns,
            # Flatten crawl_policy so adapters can read stop_on_403 etc. directly
            "enabled": self.status == "active",
            "max_pages_per_run": self.crawl_policy.max_pages_per_run,
            "request_delay_seconds": self.crawl_policy.request_delay_seconds,
            "max_documents_per_run": self.crawl_policy.max_documents_per_run,
            "respect_robots": self.crawl_policy.respect_robots,
            "stop_on_403": self.crawl_policy.stop_on_403,
            "stop_on_429": self.crawl_policy.stop_on_429,
        }


# ─── PIB seed entry ───────────────────────────────────────────────────────────
# Canonical seed for the Press Information Bureau (Day-1 target).
# Insert this into the `sources` collection on first startup.

PIB_SOURCE = Source(
    source_id="pib",
    name="Press Information Bureau",
    base_domains=["pib.gov.in", "www.pib.gov.in", "static.pib.gov.in"],
    seed_urls=[
        "https://www.pib.gov.in/Allrel.aspx?reg=48&lang=1",
    ],
    adapter="pib",
    government_level="central",
    state=None,
    allowed_document_types=["press_release", "fact_sheet", "press_note"],
    allowed_path_patterns=[
        "/PressReleaseDetail.aspx",
        "/FactsheetDetails.aspx",
        "/PressNoteDetails.aspx",
        "/Allrel.aspx",
    ],
    crawl_policy=CrawlPolicy(
        max_pages_per_run=5,
        request_delay_seconds=5,
        max_documents_per_run=50,
        respect_robots=True,
        stop_on_403=True,
        stop_on_429=True,
    ),
    status="active",
)


# ─── Request / response models ────────────────────────────────────────────────

class CrawlRunRequest(BaseModel):
    """Body for POST /api/admin/sources/{source_id}/crawl."""
    max_pages: int = 5
    max_documents: int = 50


class CrawlRun(BaseModel):
    """Result / status record for a single crawler run."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    status: str = "pending"   # pending | running | completed | failed
    pages_fetched: int = 0
    documents_discovered: int = 0
    documents_new: int = 0
    documents_duplicate: int = 0
    blocked_requests: int = 0
    errors: list[dict] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
