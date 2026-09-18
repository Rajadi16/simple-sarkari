"""
Circular model — a normalized government document based on the CanonicalCircular schema.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from lib.dates import utcnow


class SourceBlock(BaseModel):
    source_id: str
    source_name: str
    source_domain: str
    source_url: str
    discovered_from_url: str | None = None
    official_document_url: str | None = None
    source_reference_id: str | None = None


class ClassificationBlock(BaseModel):
    government_level: str = "central"
    state: str | None = None
    department: str | None = None
    document_type: str | None = None
    category: str | None = None
    sub_category: str | None = None
    language: str = "en-IN"


class IdentityBlock(BaseModel):
    title_original: str
    document_number: str | None = None
    reference_number: str | None = None
    gazette_number: str | None = None
    subject_original: str | None = None


class DatesBlock(BaseModel):
    published_date: str | None = None
    effective_from: str | None = None
    effective_until: str | None = None
    last_updated: str | None = None
    date_text_original: str | None = None


class Section(BaseModel):
    heading: str | None = None
    text: str
    page_start: int | None = None
    page_end: int | None = None


class ContentBlock(BaseModel):
    original_text: str | None = None
    clean_text: str | None = None
    sections: list[Section] = Field(default_factory=list)


class Attachment(BaseModel):
    url: str
    type: str
    title: str | None = None
    file_size_bytes: int | None = None
    s3_key: str | None = None


class ProvenanceBlock(BaseModel):
    retrieved_at: str | None = None
    retrieval_timezone: str | None = None
    http_status: int | None = None
    content_hash: str | None = None
    raw_html_s3_key: str | None = None
    raw_pdf_s3_key: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    robots_checked: bool = False
    terms_checked: bool = False


class ExtractionBlock(BaseModel):
    status: str = "pending"
    method: str | None = None
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ProcessingBlock(BaseModel):
    status: str = "extracted"
    published: bool = False
    translation_languages: list[str] = Field(default_factory=list)


class SimplificationBlock(BaseModel):
    """AI output fields added to the canonical schema."""
    simplified_title: str | None = None
    summary: str | None = None
    simplified_text: str | None = None
    required_action: str | None = None
    who_is_affected: str | None = None
    important_dates: list[dict] = Field(default_factory=list)
    amounts: list[dict] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class Circular(BaseModel):
    """The complete Canonical Circular document."""
    schema_version: str = "1.0"
    id: str = Field(default="")
    
    source: SourceBlock
    classification: ClassificationBlock
    identity: IdentityBlock
    dates: DatesBlock
    content: ContentBlock
    attachments: list[Attachment] = Field(default_factory=list)
    provenance: ProvenanceBlock
    extraction: ExtractionBlock
    processing: ProcessingBlock
    
    simplification: SimplificationBlock | None = None
    source_specific_metadata: dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
