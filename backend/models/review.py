"""
Review model — tracks human review decisions for translations.
"""

from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from lib.dates import utcnow


class Review(BaseModel):
    """A reviewer's assessment of a translation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circular_id: str
    translation_id: str
    language: str

    # Review state
    status: str = "draft"
    # draft | in_review | changes_requested | approved | rejected | published

    # Reviewer edits
    simplified_title: str | None = None
    simplified_text: str | None = None
    translation_text: str | None = None
    reviewer_notes: str | None = None
    risk_tags: list[str] = Field(default_factory=list)

    # Assigned reviewer
    assigned_to: str | None = None

    # Audit
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReviewEditRequest(BaseModel):
    """Body for PATCH /api/admin/reviews/{review_id}."""
    simplified_title: str | None = None
    simplified_text: str | None = None
    translation_text: str | None = None
    reviewer_notes: str | None = None
    risk_tags: list[str] | None = None


class ReviewRedraftRequest(BaseModel):
    """Body for POST /api/admin/reviews/{review_id}/redraft."""
    feedback: str


class ReviewRejectRequest(BaseModel):
    """Body for POST /api/admin/reviews/{review_id}/reject."""
    reason: str
