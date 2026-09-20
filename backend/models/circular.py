"""
Canonical circular models — the handoff contract between Person 1 and Team 3.

Matches CONTEXT.md §4.1 (CandidateDocument) and §4.2 (CanonicalCircular) exactly.

Person 1 (Aditya) owns the shape defined here.
Team 3 should only ADD sub-objects (translation/review/audio) — never rename
or remove fields defined below.

DO NOT touch ai_service.py, translation_service.py, audio_service.py, or
routers/review.py — those belong to Team 3.
"""

from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from lib.dates import utcnow


# ─── §4.1 Discovery stage ─────────────────────────────────────────────────────

class CandidateDocument(BaseModel):
    """
    Logged the moment the crawler finds a link, before fetch/parse.
    Internal to Person 1's pipeline; makes broken links distinguishable
    from broken parsers when something goes wrong.
    """
    source_id: str
    detail_url: str
    document_url: Optional[str] = None
    title: Optional[str] = None
    published_date_text: Optional[str] = None
    document_type: Optional[str] = None
    department: Optional[str] = None
    language: str = "en-IN"
    discovered_from_url: Optional[str] = None
    source_reference_id: Optional[str] = None


# ─── §4.2 Handoff stage — nested sub-objects ─────────────────────────────────

class SourceInfo(BaseModel):
    source_id: str
    source_name: str
    source_domain: str
    source_url: str
    discovered_from_url: Optional[str] = None
    official_document_url: Optional[str] = None
    source_reference_id: Optional[str] = None


class Classification(BaseModel):
    government_level: str                          # "central" | "state"
    state: Optional[str] = None
    department: str = "Unknown"                    # required per §4.4
    document_type: str = "circular"               # required per §4.4
    category: Optional[str] = None
    sub_category: Optional[str] = None
    language: str = "en-IN"


class Identity(BaseModel):
    title_original: str
    document_number: Optional[str] = None
    reference_number: Optional[str] = None
    gazette_number: Optional[str] = None
    subject_original: Optional[str] = None


class Dates(BaseModel):
    published_date: Optional[str] = None          # ISO 8601 date string, e.g. "2026-06-01"
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    last_updated: Optional[str] = None
    date_text_original: Optional[str] = None       # Raw text as it appeared on the page


class ContentSection(BaseModel):
    heading: Optional[str] = None
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class Content(BaseModel):
    original_text: str = ""                        # required per §4.4 — never null
    clean_text: Optional[str] = None               # Nav/boilerplate stripped version
    sections: list[ContentSection] = Field(default_factory=list)


class Attachment(BaseModel):
    url: str
    type: str                                      # "pdf" | "doc" | "image" | ...
    title: Optional[str] = None
    file_size_bytes: Optional[int] = None
    s3_key: Optional[str] = None                   # raw/{id}/v{n}/original.pdf


class Provenance(BaseModel):
    retrieved_at: Optional[datetime] = None
    retrieval_timezone: str = "Asia/Kolkata"
    http_status: Optional[int] = None              # null for pasted-text path
    content_hash: Optional[str] = None             # "sha256:<hex>"
    raw_html_s3_key: Optional[str] = None          # raw/{id}/v1/original.html
    raw_pdf_s3_key: Optional[str] = None           # raw/{id}/v1/original.pdf
    parser_name: Optional[str] = None
    parser_version: Optional[str] = None
    robots_checked: bool = False
    terms_checked: bool = False


class Extraction(BaseModel):
    status: str = "complete"                       # "complete" | "partial" | "failed"
    method: Optional[str] = "html"                 # "html" | "pdf" | "text"
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class Processing(BaseModel):
    """
    Processing state machine.
    """
    status: str = "extracted"
    published: bool = False
    email_dispatched: bool = False
    translation_languages: list[str] = Field(default_factory=list)


class SimplificationBlock(BaseModel):
    """AI output fields added to the canonical schema."""
    urgency_level: str = Field(default="low", description="low, medium, or high")
    simplified_title: Optional[str] = None
    summary: Optional[str] = None
    simplified_text: Optional[str] = None
    required_action: Optional[str] = None
    who_is_affected: Optional[str] = None
    important_dates: list[dict] = Field(default_factory=list)
    amounts: list[dict] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    deadlines: list[dict] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


# ─── §4.2 CanonicalCircular — the full handoff document ──────────────────────

class CanonicalCircular(BaseModel):
    """
    The document written to MongoDB's `circulars` collection after extraction.
    """
    schema_version: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # e.g. "50c609f1-..."

    source: SourceInfo
    classification: Classification
    identity: Identity
    dates: Dates = Field(default_factory=Dates)
    content: Content
    attachments: list[Attachment] = Field(default_factory=list)
    provenance: Provenance
    extraction: Extraction = Field(default_factory=Extraction)
    processing: Processing = Field(default_factory=Processing)
    
    simplification: Optional[SimplificationBlock] = None
    source_specific_metadata: dict[str, Any] = Field(default_factory=dict)

    # Mongo timestamps — managed by the service layer
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ─── Legacy flat model removed — Team 3 code must be updated to CanonicalCircular ───────

