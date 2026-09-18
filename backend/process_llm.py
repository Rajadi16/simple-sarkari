import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from motor.motor_asyncio import AsyncIOMotorClient
from config import get_settings
from services.ai_service import process_simplification
from services.translation_service import create_translations

async def main():
    print("Connecting to DB...")
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_url)
    
    # For testing, we use the test DB so it finds the document scraped by test_pipeline.py
    # Change to settings.db_name if you want to use the main database
    db = client[settings.db_name + "_test"] 
    
    # Find a document that has been extracted but not yet simplified
    print("Finding a document to process...")
    doc = await db.circulars.find_one({"processing.status": "extracted"})
    
    if not doc:
        print("No documents found with status 'extracted'. Run test_pipeline.py first to scrape one!")
        return
        
    circular_id = doc["id"]
    print(f"Found document: {circular_id} - {doc['identity']['title_original']}")
    
    # 1. Simplification
    print("\n--- Running AI Simplification (Claude 3 Haiku) ---")
    try:
        await process_simplification(db, circular_id)
        print("Simplification complete!")
    except Exception as e:
        print(f"Simplification failed (ensure AWS credentials are set): {e}")
        return
    
    # 2. Translation
    print("\n--- Running AI Translation (Claude 3 Haiku) to Hindi and Kannada ---")
    languages = ["hi-IN", "kn-IN"]
    try:
        translation_ids = await create_translations(db, circular_id, languages)
        print(f"Translation complete! Created translations: {translation_ids}")
    except Exception as e:
        print(f"Translation failed: {e}")
        return
    
    # Verification
    updated_doc = await db.circulars.find_one({"id": circular_id})
    print("\n--- Final Document State ---")
    print(f"Status: {updated_doc['processing']['status']}")
    if 'simplification' in updated_doc and updated_doc['simplification']:
        print(f"Simplified Title: {updated_doc['simplification'].get('simplified_title')}")
        print(f"Summary: {updated_doc['simplification'].get('summary')}")
    
    print("\nTranslations have been sent to the 'translations' and 'reviews' collections as drafts.")

if __name__ == "__main__":
    asyncio.run(main())
