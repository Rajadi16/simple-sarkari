"""
Audio worker — background task for Polly TTS generation.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.audio_service import create_audio_asset

logger = logging.getLogger(__name__)

async def run_audio_generation(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> None:
    """
    Background task: generate audio for an approved translation.
    """
    try:
        await create_audio_asset(db, circular_id, language)
        logger.info(f"Successfully generated audio for {circular_id} in {language}")
    except Exception as e:
        logger.error(f"Failed to generate audio for {circular_id} in {language}: {e}")
