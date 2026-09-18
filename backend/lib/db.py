"""
MongoDB async client via Motor.

Connection lifecycle is managed through the FastAPI lifespan context.
Use `get_db()` as a FastAPI dependency to access the database.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import get_settings

# Module-level references — initialized in lifespan, not at import time.
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """Call once during application startup (lifespan)."""
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo_url)
    _db = _client[settings.db_name]
    await _create_indexes()


async def close_db() -> None:
    """Call once during application shutdown (lifespan)."""
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency — returns the active database handle."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db


async def _create_indexes() -> None:
    """
    Ensure required indexes exist.
    Called once on startup — idempotent.
    """
    db = get_db()

    # circulars
    await db.circulars.create_index("content_hash", unique=True, sparse=True)
    await db.circulars.create_index([("source_id", 1), ("published_at", -1)])
    await db.circulars.create_index([("published", 1), ("published_at", -1)])
    await db.circulars.create_index([("department", 1), ("published_at", -1)])
    await db.circulars.create_index(
        [("government_level", 1), ("state", 1), ("published_at", -1)]
    )
    await db.circulars.create_index(
        [("title", "text"), ("subject", "text"), ("department", "text"),
         ("original_text", "text"), ("simplified_text", "text")],
        name="circulars_text_search",
    )

    # translations
    await db.translations.create_index(
        [("circular_id", 1), ("language", 1), ("revision", 1)], unique=True
    )
    await db.translations.create_index([("status", 1), ("created_at", -1)])

    # reviews
    await db.reviews.create_index([("status", 1), ("created_at", -1)])
    await db.reviews.create_index([("assigned_to", 1), ("status", 1)])

    # jobs
    await db.jobs.create_index("idempotency_key", unique=True, sparse=True)
    await db.jobs.create_index([("status", 1), ("created_at", -1)])

    # audio_assets
    await db.audio_assets.create_index(
        [("circular_id", 1), ("language", 1)], unique=True
    )

    # audit_events
    await db.audit_events.create_index([("created_at", -1)])
    await db.audit_events.create_index([("entity_type", 1), ("entity_id", 1)])
