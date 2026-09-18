"""
Provenance / audit service — logs every important action.

Every human decision and system event gets an immutable audit record.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from lib.dates import utcnow


async def log_event(
    db: AsyncIOMotorDatabase,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    details: dict | None = None,
) -> str:
    """
    Create an immutable audit event.

    TODO: Implement:
      1. Insert into audit_events collection
      2. Return the event ID
    """
    raise NotImplementedError("log_event")


async def get_events(
    db: AsyncIOMotorDatabase,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Retrieve audit events, newest first.

    TODO: Implement query with optional entity filters.
    """
    raise NotImplementedError("get_events")
