"""
Translation worker — background task for AI simplification + translation.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def run_translation(db: AsyncIOMotorDatabase, circular_id: str, languages: list[str]) -> None:
    """
    Background task: simplify and translate a circular.

    TODO:
      1. Call ai_service.process_simplification()
      2. Call translation_service.create_translations()
      3. Update processing_status
    """
    raise NotImplementedError("run_translation")
