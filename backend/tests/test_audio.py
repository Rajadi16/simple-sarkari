import pytest
import uuid

from config import get_settings
from services.audio_service import create_audio_asset

from mongomock_motor import AsyncMongoMockClient

@pytest.fixture
async def test_db():
    client = AsyncMongoMockClient()
    db = client.get_database("sarkari_test")
    yield db
    
    # Cleanup
    await db.translations.delete_many({})
    await db.audio_assets.delete_many({})

@pytest.mark.asyncio
async def test_create_audio_asset(test_db, mocker):
    # Mock the AWS calls
    mock_polly = mocker.patch("services.audio_service.get_polly_client")
    mock_polly.return_value.synthesize_speech.return_value = {
        "AudioStream": mocker.MagicMock(read=lambda: b"dummy mp3 data")
    }
    
    mock_upload = mocker.patch("services.audio_service.upload_to_s3", new_callable=mocker.AsyncMock)
    mock_upload.return_value = "audio/mock_key.mp3"
    
    mock_signed_url = mocker.patch("services.audio_service.generate_signed_url")
    mock_signed_url.return_value = "https://mock-signed-url.com"

    circular_id = f"circular_{uuid.uuid4()}"
    translation_id = str(uuid.uuid4())
    
    dummy_translation = {
        "_id": translation_id,
        "id": translation_id,
        "circular_id": circular_id,
        "language": "hi-IN",
        "revision": 1,
        "status": "approved",
        "translated_text": "यह एक परीक्षण संदेश है।"
    }
    
    await test_db.translations.insert_one(dummy_translation)
    
    result = await create_audio_asset(test_db, circular_id, "hi-IN")
    
    assert result["status"] == "ready"
    assert result["url"] == "https://mock-signed-url.com"
    
    # Verify the asset was saved to the DB
    asset = await test_db.audio_assets.find_one({"circular_id": circular_id})
    assert asset is not None
    assert asset["status"] == "ready"
    expected_s3_key = f"audio/{circular_id}/hi-IN/v1.mp3"
    assert asset["s3_key"] == expected_s3_key
    
    # Verify the AWS mocks were called correctly
    mock_polly.return_value.synthesize_speech.assert_called_once()
    mock_upload.assert_called_once()
    mock_signed_url.assert_called_once()
