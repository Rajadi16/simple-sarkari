"""
Audio asset model — metadata for generated speech files.
"""

import uuid

from pydantic import BaseModel, Field
from datetime import datetime
from lib.dates import utcnow


class AudioAsset(BaseModel):
    """Metadata for a Polly-generated audio file stored in S3."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circular_id: str
    translation_id: str
    language: str  # e.g. "hi-IN"

    provider: str = "amazon_polly"
    voice: str | None = None
    format: str = "mp3"
    s3_key: str | None = None
    translation_revision: int = 1

    status: str = "pending"  # pending | generating | ready | failed
    error_message: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
