"""
Audio service — Amazon Polly TTS and S3 storage.

Responsibilities:
  - Generate speech from approved translations
  - Upload MP3 to S3
  - Create audio metadata records
  - Generate signed playback URLs
  - Handle unsupported languages gracefully
"""

from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.aws import get_polly_client, upload_to_s3, generate_signed_url


# Supported Polly voices per language
POLLY_VOICES: dict[str, dict] = {
    "hi-IN": {"voice_id": "Kajal", "engine": "neural"},
    "en-IN": {"voice_id": "Kajal", "engine": "neural"},
    # Add more as Polly support expands
    # "kn-IN" is not natively supported — audio will be unavailable
}


def is_language_supported(language: str) -> bool:
    """Check if Polly supports the given language."""
    return language in POLLY_VOICES


async def generate_audio(text: str, language: str) -> bytes | None:
    """
    Generate MP3 audio from text using Amazon Polly.

    TODO: Implement:
      1. Check language support
      2. Call polly_client.synthesize_speech()
      3. Return MP3 bytes or None if unsupported
    """
    raise NotImplementedError("generate_audio")


async def create_audio_asset(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> dict:
    """
    Full audio generation pipeline.

    TODO:
      1. Verify translation exists and is approved
      2. Verify translation revision is current
      3. Check language support
      4. Call generate_audio
      5. Upload MP3 to S3
      6. Create AudioAsset record in DB
      7. Return audio metadata with signed URL
    """
    raise NotImplementedError("create_audio_asset")


async def get_audio_url(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> dict:
    """
    Get a signed playback URL for existing audio.

    TODO:
      1. Look up AudioAsset in DB
      2. Verify status is "ready"
      3. Generate and return signed URL
    """
    raise NotImplementedError("get_audio_url")
