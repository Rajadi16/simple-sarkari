import pytest
from services.translation_service import translate_text

@pytest.mark.asyncio
async def test_translate_text():
    mock_text = (
        "The Government of India has announced a new scholarship program for female students "
        "pursuing higher education in STEM fields. Applications open on November 1st and "
        "close on December 31st. An amount of Rs. 50,000 per year will be provided."
    )
    
    hindi_text = await translate_text(mock_text, "Hindi")
    assert hindi_text is not None
    assert len(hindi_text) > 0
    
    kannada_text = await translate_text(mock_text, "Kannada")
    assert kannada_text is not None
    assert len(kannada_text) > 0
