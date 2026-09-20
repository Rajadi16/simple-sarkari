import pytest
import json
from unittest.mock import MagicMock, patch
from services.ai_service import simplify_document

@pytest.mark.asyncio
async def test_simplify_document():
    mock_text = """
    GOVERNMENT OF INDIA
    MINISTRY OF FINANCE
    
    OFFICE MEMORANDUM
    
    Subject: Disbursement of Dearness Allowance to Central Government Employees - Revised Rates effective from 01.07.2023.
    
    The undersigned is directed to refer to this Ministry's Office Memorandum No. 1/1/2023-E-II (B) dated 03.04.2023 on the subject mentioned above and to say that the President is pleased to decide that the Dearness Allowance payable to Central Government employees shall be enhanced from the existing rate of 42% to 46% of the Basic Pay with effect from 1st July, 2023.
    """

    mock_ai_response = {
        "summary": "Dearness Allowance increased from 42% to 46% for central government employees.",
        "who_is_affected": "Central Government employees.",
        "required_action": "No action required.",
        "important_dates": [],
        "amounts": [{"amount": "46%", "description": "New DA rate"}],
        "eligibility": ["Central Government employees"],
        "warnings": [],
        "simplified_title": "DA Hike for Central Govt Employees",
        "simplified_text": "The government has raised dearness allowance from 42% to 46%.",
        "keywords": ["dearness allowance", "central government"],
        "source_excerpts": [],
    }

    with patch("services.ai_service.get_bedrock_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(mock_ai_response)}]
                }
            }
        }

        result = await simplify_document(mock_text)

    assert result is not None
    assert result.summary is not None
    assert len(result.summary) > 0
    assert result.who_is_affected is not None
