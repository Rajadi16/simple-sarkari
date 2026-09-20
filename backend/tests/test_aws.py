import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from lib.aws import get_sqs_client, get_sagemaker_client, enqueue_message
import json

def test_get_sqs_client(mocker):
    mocker.patch("lib.aws.get_settings", return_value=MagicMock(aws_enabled=True, aws_region="us-east-1"))
    boto_mock = mocker.patch("boto3.client")
    
    # reset global state just in case
    import lib.aws
    lib.aws._sqs_client = None
    
    client = get_sqs_client()
    boto_mock.assert_called_with("sqs", region_name="us-east-1")
    assert client == boto_mock.return_value

def test_get_sagemaker_client(mocker):
    mocker.patch("lib.aws.get_settings", return_value=MagicMock(aws_enabled=True, aws_region="us-east-1"))
    boto_mock = mocker.patch("boto3.client")
    
    # reset global state
    import lib.aws
    lib.aws._sagemaker_client = None
    
    client = get_sagemaker_client()
    boto_mock.assert_called_with("sagemaker-runtime", region_name="us-east-1")
    assert client == boto_mock.return_value

@pytest.mark.asyncio
async def test_enqueue_message(mocker):
    mock_settings = MagicMock(aws_sqs_queue_url="https://sqs.aws.com/queue")
    mocker.patch("lib.aws.get_settings", return_value=mock_settings)
    
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "12345"}
    mocker.patch("lib.aws.get_sqs_client", return_value=mock_sqs)
    
    msg_id = await enqueue_message("test_type", {"foo": "bar"})
    
    assert msg_id == "12345"
    mock_sqs.send_message.assert_called_once()
    kwargs = mock_sqs.send_message.call_args[1]
    assert kwargs["QueueUrl"] == "https://sqs.aws.com/queue"
    body = json.loads(kwargs["MessageBody"])
    assert body["message_type"] == "test_type"
    assert body["payload"] == {"foo": "bar"}
