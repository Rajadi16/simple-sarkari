"""
Audio service — Amazon Polly TTS and S3 storage.

Responsibilities:
  - Generate speech from approved translations
  - Upload MP3 to S3
  - Create audio metadata records
  - Generate signed playback URLs
  - Handle unsupported languages gracefully
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.aws import get_polly_client, upload_to_s3, generate_signed_url
from models.audio import AudioAsset

logger = logging.getLogger(__name__)


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
    """
    if not is_language_supported(language):
        logger.info(f"Language {language} is not supported by Polly.")
        return None
        
    polly = get_polly_client()
    voice = POLLY_VOICES[language]["voice_id"]
    engine = POLLY_VOICES[language]["engine"]
    
    try:
        response = await asyncio.to_thread(
            polly.synthesize_speech,
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice,
            Engine=engine,
            LanguageCode=language,
        )
        if "AudioStream" in response:
            with response["AudioStream"] as stream:
                return stream.read()
    except Exception as e:
        logger.error(f"Polly synthesis failed for language {language}: {e}")
        return None
        
    return None


async def create_audio_asset(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> dict:
    """
    Full audio generation pipeline.
    """
    translation_doc = await db.translations.find_one(
        {"circular_id": circular_id, "language": language, "status": "approved"},
        sort=[("revision", -1)]
    )
    if not translation_doc:
        raise ValueError(f"No approved translation found for {circular_id} in {language}")
        
    text = translation_doc.get("translated_text")
    if not text:
        raise ValueError(f"Translation text is empty for {circular_id} in {language}")
        
    existing_audio = await db.audio_assets.find_one({
        "circular_id": circular_id, 
        "language": language, 
        "translation_revision": translation_doc["revision"]
    })
    
    if existing_audio and existing_audio.get("status") == "ready":
        url = generate_signed_url(existing_audio["s3_key"])
        return {**existing_audio, "url": url}

    audio_bytes = await generate_audio(text, language)
    if not audio_bytes:
        asset = AudioAsset(
            circular_id=circular_id,
            translation_id=str(translation_doc.get("_id", translation_doc.get("id"))),
            language=language,
            translation_revision=translation_doc["revision"],
            status="failed",
            error_message="Language unsupported or synthesis failed"
        )
        await db.audio_assets.insert_one(asset.model_dump(by_alias=True))
        return asset.model_dump()
        
    s3_key = f"audio/{circular_id}/{language}/v{translation_doc['revision']}.mp3"
    await upload_to_s3(s3_key, audio_bytes, "audio/mpeg")
    
    asset = AudioAsset(
        circular_id=circular_id,
        translation_id=str(translation_doc.get("_id", translation_doc.get("id"))),
        language=language,
        voice=POLLY_VOICES[language]["voice_id"],
        s3_key=s3_key,
        translation_revision=translation_doc["revision"],
        status="ready"
    )
    asset_dict = asset.model_dump(by_alias=True)
    
    if "_id" not in asset_dict:
        asset_dict["_id"] = asset_dict["id"]
        
    await db.audio_assets.insert_one(asset_dict)
    
    url = generate_signed_url(s3_key)
    return {**asset_dict, "url": url}


async def get_audio_url(db: AsyncIOMotorDatabase, circular_id: str, language: str) -> dict:
    """
    Get a signed playback URL for existing audio.
    """
    asset_doc = await db.audio_assets.find_one(
        {"circular_id": circular_id, "language": language, "status": "ready"},
        sort=[("translation_revision", -1)]
    )
    if not asset_doc:
        raise ValueError(f"No ready audio asset found for {circular_id} in {language}")
        
    url = generate_signed_url(asset_doc["s3_key"])
    
    # Handle ObjectId serialization if needed
    if "_id" in asset_doc:
        asset_doc["_id"] = str(asset_doc["_id"])
        
    return {**asset_doc, "url": url}
