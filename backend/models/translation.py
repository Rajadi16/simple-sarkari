"""
Translation model — one record per language per revision of a circular.
"""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from lib.dates import utcnow


class Translation(BaseModel):
    """AI-generated translation of a circular, subject to human review."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circular_id: str
    language: str  # e.g. "hi-IN", "kn-IN", "en-IN"
    revision: int = 1

    translated_title: str | None = None
    translated_text: str | None = None
    translated_summary: str | None = None

    # AI provenance
    model_id: str | None = None
    prompt_version: str | None = None

    # Status
    status: str = "draft"
    # draft | in_review | changes_requested | approved | rejected | translation_failed

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class TranslationRequest(BaseModel):
    """Body for POST /api/admin/circulars/{circular_id}/translations."""
    languages: list[str] = Field(..., min_length=1, examples=[["en-IN", "hi-IN", "kn-IN"]])
