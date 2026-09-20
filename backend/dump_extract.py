import asyncio
import json
from crawlers.drupal_karnataka import DrupalKarnatakaAdapter
from models.circular import CanonicalCircular

# Create a mock source dict for BESCOM as in test_crawlers.py
BESCOM_SOURCE = {
    "source_id": "bescom", "name": "BESCOM", "adapter": "drupal_karnataka",
    "base_domains": ["bescom.karnataka.gov.in"], "government_level": "state",
    "state": "Karnataka", "department": "BESCOM",
    "category": "utilities",
    "seed_urls": ["https://bescom.karnataka.gov.in/43/circulars/en"],
    "stop_on_403": True, "stop_on_429": True, "respect_robots": True,
    "request_delay_seconds": 2, "max_documents_per_run": 3,
}

from crawlers.source_config import normalize_source_config
BESCOM_SOURCE = normalize_source_config(BESCOM_SOURCE)

async def main():
    adapter = DrupalKarnatakaAdapter(BESCOM_SOURCE)
    try:
        candidates = await adapter.fetch_listing()
        if not candidates:
            print("No candidates found.")
            return

        print(f"Found {len(candidates)} candidates. Fetching the first one...")
        candidate = candidates[0]
        fetched = await adapter.fetch_detail(candidate)
        circular = await adapter.parse(candidate, fetched)
        
        # Save to markdown
        with open("C:/Users/Sanjana/.gemini/antigravity-ide/brain/cdb63786-cda0-416c-8779-5bd74c51a9e4/extracted_content.md", "w", encoding="utf-8") as f:
            f.write("# Extracted Content (BESCOM)\n\n")
            f.write(f"**Title**: {circular.identity.title_original}\n\n")
            f.write(f"**URL**: {circular.source.source_url}\n\n")
            f.write(f"**Document URL**: {circular.source.official_document_url}\n\n")
            f.write("## Original Text\n\n")
            f.write("```text\n")
            f.write(circular.content.original_text)
            f.write("\n```\n")
        
        print("Done! Extracted content written to extracted_content.md")
    finally:
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(main())
