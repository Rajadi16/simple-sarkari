import pytest
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
    
    result = await simplify_document(mock_text)
    
    assert result is not None
    assert result.summary is not None
    assert len(result.summary) > 0
    assert result.who_is_affected is not None
