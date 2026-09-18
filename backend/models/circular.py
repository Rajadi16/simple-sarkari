"""
Circular model — a normalized government document.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from lib.dates import utcnow


class Circular(BaseModel):
    """A single government circular / notification / order."""
    id: str = Field(default="")
    source_id: str
    source_url: str
    content_hash: str | None = None

    # Original content
    title: str
    subject: str | None = None
    department: str | None = None
    document_type: str | None = None  # press_release, order, circular, notification, gazette
    government_level: str = "central"  # central | state
    state: str | None = None
    original_language: str = "en-IN"
    original_text: str | None = None

    # AI-simplified content (English)
    simplified_title: str | None = None
    simplified_text: str | None = None
    summary: str | None = None
    who_is_affected: str | None = None
    required_action: str | None = None
    important_dates: list[dict] = Field(default_factory=list)
    amounts: list[dict] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    # S3 references
    raw_s3_key: str | None = None
    extracted_s3_key: str | None = None

    # Processing state machine
    processing_status: str = "discovered"
    # discovered → fetch_queued → fetched → extracted → ai_draft_generated
    # → translation_generated → in_review → approved → audio_queued
    # → audio_ready → published
    # Failure: blocked_by_robots | blocked_by_source | rate_limited
    #          fetch_failed | parse_failed | ocr_failed | translation_failed
    #          review_rejected | audio_failed

    # Publication
    published: bool = False
    published_at: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DocumentVersion(BaseModel):
    """Immutable snapshot when a source document changes."""
    id: str = Field(default="")
    circular_id: str
    version: int = 1
    content_hash: str
    raw_s3_key: str
    extracted_text: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
