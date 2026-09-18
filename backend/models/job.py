"""
Job model — tracks background processing tasks.
"""

import uuid

from pydantic import BaseModel, Field
from datetime import datetime
from lib.dates import utcnow


class Job(BaseModel):
    """A background processing job (crawl, extraction, translation, audio)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: str  # crawl | extraction | translation | audio
    status: str = "pending"  # pending | running | completed | failed | cancelled
    document_id: str | None = None
    source_id: str | None = None
    language: str | None = None
    idempotency_key: str | None = None

    # Execution
    attempts: int = 0
    max_attempts: int = 3
    error_message: str | None = None
    result: dict | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
