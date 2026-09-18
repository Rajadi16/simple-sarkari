"""
Audio worker — background task for Polly TTS generation.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def run_audio_generation(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> None:
    """
    Background task: generate audio for an approved translation.

    TODO: Delegate to audio_service.create_audio_asset()
    """
    raise NotImplementedError("run_audio_generation")
