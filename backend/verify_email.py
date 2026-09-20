import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from models.circular import CanonicalCircular
from workers.mailing_worker import process_pending_urgent_emails
from config import get_settings

async def main():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    
    # 1. Create a dummy circular
    dummy_circular = {
        "id": "test-urgent-123",
        "url": "http://example.com",
        "hash": "abc",
        "provenance": {
            "source_id": "test",
            "source_name": "Test",
            "department": "Test Dept",
            "document_type": "circular"
        },
        "source_metadata": {
            "title": "Test Title",
            "department_name": "Test Dept",
            "type": "circular",
            "government_level": "central"
        },
        "extracted_text": "Sample",
        "processing": {
            "status": "extracted",
            "published": True,
            "email_dispatched": False,
            "translation_languages": []
        },
        "simplification": {
            "urgency_level": "high",
            "simplified_title": "Test Title",
            "summary": "This is a test summary."
        },
        "translations": {},
        "audio": {}
    }
    
    await db.circulars.update_one(
        {"id": dummy_circular["id"]}, 
        {"$set": dummy_circular}, 
        upsert=True
    )
    
    print("Inserted mock urgent circular.")
    
    # Run the worker (this will attempt to use SES)
    print("Running worker...")
    
    # We will temporarily patch send_urgent_circular_email so it doesn't fail on missing AWS creds
    import workers.mailing_worker
    original_send = workers.mailing_worker.send_urgent_circular_email
    
    def mock_send(circular):
        print(f"MOCK: Sending email for {circular.id}")
        return True
        
    workers.mailing_worker.send_urgent_circular_email = mock_send
    
    try:
        sent = await process_pending_urgent_emails(db)
        print(f"Worker finished. Emails sent: {sent}")
        
        # Verify db state
        updated = await db.circulars.find_one({"id": "test-urgent-123"})
        if updated and updated["processing"]["email_dispatched"] == True:
            print("SUCCESS: email_dispatched flag was flipped to True")
        else:
            print("ERROR: flag was not flipped")
            
    finally:
        workers.mailing_worker.send_urgent_circular_email = original_send
        await db.circulars.delete_one({"id": "test-urgent-123"})

if __name__ == "__main__":
    asyncio.run(main())
