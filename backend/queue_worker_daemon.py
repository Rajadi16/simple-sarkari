import asyncio
import json
import logging
import traceback
from botocore.exceptions import ClientError

from config import get_settings
from lib.db import get_db, connect_to_mongo, close_mongo_connection
from lib.aws import get_sqs_client
from workers.ingestion_worker import process_url_ingestion, process_text_ingestion, process_crawl_run

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("queue_worker_daemon")

async def process_message(db, message_body: dict):
    """Dispatch the message to the appropriate worker based on message_type."""
    message_type = message_body.get("message_type")
    payload = message_body.get("payload", {})
    
    logger.info(f"Processing message_type: {message_type}")

    if message_type == "url_ingestion":
        await process_url_ingestion(
            db=db,
            job_id=payload["job_id"],
            url=payload["url"],
            source_id=payload["source_id"]
        )
    elif message_type == "text_ingestion":
        await process_text_ingestion(
            db=db,
            job_id=payload["job_id"],
            data=payload["data"]
        )
    elif message_type == "crawl_run":
        await process_crawl_run(
            db=db,
            run_id=payload["run_id"],
            source_id=payload["source_id"],
            max_pages=payload["max_pages"],
            max_documents=payload["max_documents"]
        )
    else:
        logger.warning(f"Unknown message_type: {message_type}")

async def run_worker():
    """Main long-polling loop for the SQS queue."""
    logger.info("Starting SQS worker daemon...")
    settings = get_settings()
    
    if not settings.aws_sqs_queue_url:
        logger.error("SQS Queue URL not configured (aws_sqs_queue_url)")
        return
        
    await connect_to_mongo()
    
    # get_db is an async generator, we can get the db object using anext or direct logic
    # Actually get_db yields db.
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    
    sqs = get_sqs_client()
    queue_url = settings.aws_sqs_queue_url
    
    logger.info(f"Listening to SQS Queue: {queue_url}")
    
    while True:
        try:
            # Long polling
            response = await asyncio.to_thread(
                sqs.receive_message,
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20
            )
            
            messages = response.get("Messages", [])
            for msg in messages:
                receipt_handle = msg["ReceiptHandle"]
                body_str = msg.get("Body", "{}")
                
                try:
                    body_data = json.loads(body_str)
                    await process_message(db, body_data)
                    
                    # Delete the message after successful processing
                    await asyncio.to_thread(
                        sqs.delete_message,
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    logger.info("Message processed and deleted successfully.")
                except Exception as exc:
                    logger.error(f"Error processing message: {exc}")
                    logger.error(traceback.format_exc())
                    # Not deleting the message here, it will return to queue after visibility timeout
                    
        except ClientError as e:
            logger.error(f"AWS ClientError: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error in polling loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
