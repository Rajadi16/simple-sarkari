import pytest
from unittest.mock import MagicMock, patch
from services.translation_service import translate_text


@pytest.mark.asyncio
async def test_translate_text():
    mock_text = (
        "The Government of India has announced a new scholarship program for female students "
        "pursuing higher education in STEM fields. Applications open on November 1st and "
        "close on December 31st. An amount of Rs. 50,000 per year will be provided."
    )

    def _make_converse_response(text):
        return {
            "output": {
                "message": {
                    "content": [{"text": text}]
                }
            }
        }

    with patch("services.translation_service.get_bedrock_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.converse.side_effect = [
            _make_converse_response("भारत सरकार ने STEM क्षेत्र में उच्च शिक्षा के लिए छात्रवृत्ति की घोषणा की।"),
            _make_converse_response("ಭಾರತ ಸರ್ಕಾರವು STEM ಕ್ಷೇತ್ರದಲ್ಲಿ ಉನ್ನತ ಶಿಕ್ಷಣಕ್ಕಾಗಿ ವಿದ್ಯಾರ್ಥಿವೇತನ ಘೋಷಿಸಿದೆ."),
        ]

        hindi_text = await translate_text(mock_text, "Hindi")
        assert hindi_text is not None
        assert len(hindi_text) > 0

        kannada_text = await translate_text(mock_text, "Kannada")
        assert kannada_text is not None
        assert len(kannada_text) > 0
