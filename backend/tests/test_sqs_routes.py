import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_trigger_crawl_enqueues_message(mocker):
    # Setup mocks
    mock_db = MagicMock()
    
    # Mock source retrieval
    mock_source = {"status": "active", "crawl_policy": {"enabled": True}}
    mocker.patch("routers.sources._get_source_or_404", return_value=mock_source)
    
    # Mock run creation
    mock_run = MagicMock(id="run_123")
    mocker.patch("services.crawler_service._create_crawl_run", return_value=mock_run)
    
    # Mock enqueue
    mock_enqueue = mocker.patch("lib.aws.enqueue_message")
    
    from routers.sources import trigger_crawl
    from models.source import CrawlRunRequest
    
    req = CrawlRunRequest(max_pages=2, max_documents=5)
    
    result = await trigger_crawl(
        source_id="test_source",
        body=req,
        db=mock_db
    )
    
    assert result["status"] == "pending"
    assert result["run_id"] == "run_123"
    
    mock_enqueue.assert_called_once_with(
        "crawl_run",
        {
            "run_id": "run_123",
            "source_id": "test_source",
            "max_pages": 2,
            "max_documents": 5,
        }
    )

@pytest.mark.asyncio
async def test_ingest_url_enqueues_message(mocker):
    mock_db = MagicMock()
    mocker.patch("routers.ingestion._create_job", return_value="job_abc")
    mock_enqueue = mocker.patch("lib.aws.enqueue_message")
    
    from routers.ingestion import ingest_url
    from routers.ingestion import UrlIngestionRequest
    
    req = UrlIngestionRequest(url="https://example.gov.in/test.pdf", source_id="src_1")
    
    result = await ingest_url(
        body=req,
        db=mock_db
    )
    
    assert result["status"] == "pending"
    assert result["job_id"] == "job_abc"
    
    mock_enqueue.assert_called_once_with(
        "url_ingestion",
        {
            "job_id": "job_abc",
            "url": "https://example.gov.in/test.pdf",
            "source_id": "src_1",
        }
    )
