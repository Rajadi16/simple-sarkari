import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_process_message_url_ingestion(mocker):
    mock_db = MagicMock()
    mock_url_processor = mocker.patch("queue_worker_daemon.process_url_ingestion", new_callable=AsyncMock)
    
    from queue_worker_daemon import process_message
    
    message = {
        "message_type": "url_ingestion",
        "payload": {
            "job_id": "job_1",
            "url": "http://test.com",
            "source_id": "src_1"
        }
    }
    
    await process_message(mock_db, message)
    
    mock_url_processor.assert_called_once_with(
        db=mock_db,
        job_id="job_1",
        url="http://test.com",
        source_id="src_1"
    )

@pytest.mark.asyncio
async def test_process_message_crawl_run(mocker):
    mock_db = MagicMock()
    mock_crawl_processor = mocker.patch("queue_worker_daemon.process_crawl_run", new_callable=AsyncMock)
    
    from queue_worker_daemon import process_message
    
    message = {
        "message_type": "crawl_run",
        "payload": {
            "run_id": "run_1",
            "source_id": "src_1",
            "max_pages": 5,
            "max_documents": 10
        }
    }
    
    await process_message(mock_db, message)
    
    mock_crawl_processor.assert_called_once_with(
        db=mock_db,
        run_id="run_1",
        source_id="src_1",
        max_pages=5,
        max_documents=10
    )

@pytest.mark.asyncio
async def test_process_message_unknown_type(mocker, caplog):
    mock_db = MagicMock()
    from queue_worker_daemon import process_message
    
    message = {
        "message_type": "unknown_type",
        "payload": {}
    }
    
    await process_message(mock_db, message)
    
    assert "Unknown message_type: unknown_type" in caplog.text
