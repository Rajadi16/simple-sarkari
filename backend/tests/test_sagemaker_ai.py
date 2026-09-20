import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json

@pytest.mark.asyncio
async def test_classify_urgency_sagemaker(mocker):
    # Mock settings
    mock_settings = MagicMock(sagemaker_endpoint_name="test-endpoint")
    mocker.patch("services.ai_service.get_settings", return_value=mock_settings)
    
    # Mock Sagemaker client
    mock_sm = MagicMock()
    
    # Create a mock response body with read()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps([{"label": "high", "score": 0.95}]).encode('utf-8')
    mock_sm.invoke_endpoint.return_value = {"Body": mock_body}
    
    mocker.patch("services.ai_service.get_sagemaker_client", return_value=mock_sm)
    
    from services.ai_service import classify_urgency_sagemaker
    
    result = await classify_urgency_sagemaker("This is a highly urgent text.")
    
    assert result == "high"
    mock_sm.invoke_endpoint.assert_called_once()
    kwargs = mock_sm.invoke_endpoint.call_args[1]
    assert kwargs["EndpointName"] == "test-endpoint"
    assert kwargs["ContentType"] == "application/json"
    
    body = json.loads(kwargs["Body"])
    assert body["inputs"] == "This is a highly urgent text."

@pytest.mark.asyncio
async def test_classify_urgency_sagemaker_no_endpoint(mocker):
    # Mock settings with no endpoint
    mock_settings = MagicMock(sagemaker_endpoint_name="")
    mocker.patch("services.ai_service.get_settings", return_value=mock_settings)
    
    from services.ai_service import classify_urgency_sagemaker
    result = await classify_urgency_sagemaker("This is a highly urgent text.")
    
    assert result == "low"
