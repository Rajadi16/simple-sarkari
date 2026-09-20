import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from botocore.exceptions import ClientError

from services.mailing_service import send_urgent_circular_email
from workers.mailing_worker import process_pending_urgent_emails
from models.circular import CanonicalCircular

@pytest.fixture
def mock_circular():
    return CanonicalCircular(
        id="test_id",
        source={
            "source_id": "test_src",
            "source_name": "Test",
            "source_domain": "test.in",
            "source_url": "http://test.in",
            "discovered_from_url": "http://test.in",
            "official_document_url": "http://test.in/doc.pdf",
        },
        classification={
            "government_level": "state",
            "department": "Test Dept",
            "document_type": "circular"
        },
        identity={
            "title_original": "Test Title"
        },
        provenance={
            "retrieval_timezone": "Asia/Kolkata"
        },
        extraction={
            "status": "complete",
        },
        content={
            "original_text": "text",
        },
        simplification={
            "simplified_title": "Simple Title",
            "summary": "This is a summary",
            "urgency_level": "high",
        }
    )

@patch("services.mailing_service.get_ses_client")
@patch("services.mailing_service.get_settings")
def test_send_urgent_circular_email_success(mock_get_settings, mock_get_ses_client, mock_circular):
    mock_settings = MagicMock()
    mock_settings.aws_enabled = True
    mock_settings.ses_sender_email = "sender@example.com"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_client.send_email.return_value = {"MessageId": "12345"}
    mock_get_ses_client.return_value = mock_client
    
    recipients = ["test1@test.com", "test2@test.com"]
    result = send_urgent_circular_email(mock_circular, recipients)
    
    assert result is True
    mock_client.send_email.assert_called_once()
    
    call_kwargs = mock_client.send_email.call_args[1]
    assert call_kwargs["Source"] == "sender@example.com"
    assert call_kwargs["Destination"]["BccAddresses"] == recipients
    assert "URGENT: Simple Title" in call_kwargs["Message"]["Subject"]["Data"]

@patch("services.mailing_service.get_settings")
def test_send_urgent_circular_email_aws_disabled(mock_get_settings, mock_circular):
    mock_settings = MagicMock()
    mock_settings.aws_enabled = False
    mock_get_settings.return_value = mock_settings
    
    result = send_urgent_circular_email(mock_circular, ["test@test.com"])
    assert result is False

@patch("services.mailing_service.get_ses_client")
@patch("services.mailing_service.get_settings")
def test_send_urgent_circular_email_batching(mock_get_settings, mock_get_ses_client, mock_circular):
    mock_settings = MagicMock()
    mock_settings.aws_enabled = True
    mock_settings.ses_sender_email = "sender@example.com"
    mock_get_settings.return_value = mock_settings
    
    mock_client = MagicMock()
    mock_client.send_email.return_value = {"MessageId": "12345"}
    mock_get_ses_client.return_value = mock_client
    
    # Generate 105 recipients (should result in 3 batches: 50, 50, 5)
    recipients = [f"test{i}@test.com" for i in range(105)]
    result = send_urgent_circular_email(mock_circular, recipients)
    
    assert result is True
    assert mock_client.send_email.call_count == 3

@pytest.mark.asyncio
@patch("workers.mailing_worker.send_urgent_circular_email")
async def test_process_pending_urgent_emails(mock_send_email, mock_circular):
    db = AsyncMock()
    
    # Mock circulars - motor's find() is synchronous and returns a cursor
    mock_cursor_circulars = AsyncMock()
    mock_cursor_circulars.to_list.return_value = [mock_circular.model_dump(mode='json')]
    
    # Use MagicMock for find() so it returns an object, not a coroutine
    mock_find = MagicMock()
    mock_find.return_value.limit.return_value = mock_cursor_circulars
    db.circulars.find = mock_find
    
    # Mock subscribers
    mock_cursor_subscribers = AsyncMock()
    mock_cursor_subscribers.to_list.return_value = [{"email": "test@test.com"}]
    db.subscribers.find = MagicMock(return_value=mock_cursor_subscribers)
    
    mock_send_email.return_value = True
    
    emails_sent = await process_pending_urgent_emails(db)
    
    assert emails_sent == 1
    mock_send_email.assert_called_once()
    db.circulars.update_one.assert_called_once_with(
        {"id": "test_id"},
        {"$set": {"processing.email_dispatched": True}}
    )

@pytest.mark.asyncio
async def test_process_pending_urgent_emails_no_circulars():
    db = AsyncMock()
    
    mock_cursor_circulars = AsyncMock()
    mock_cursor_circulars.to_list.return_value = []
    
    mock_find = MagicMock()
    mock_find.return_value.limit.return_value = mock_cursor_circulars
    db.circulars.find = mock_find
    
    emails_sent = await process_pending_urgent_emails(db)
    assert emails_sent == 0
