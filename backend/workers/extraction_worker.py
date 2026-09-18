"""
Extraction worker — background task for HTML/PDF text extraction.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def run_extraction(db: AsyncIOMotorDatabase, circular_id: str) -> None:
    """
    Background task: extract text from a raw document.

    TODO: Delegate to extraction_service.process_extraction()
    """
    raise NotImplementedError("run_extraction")
