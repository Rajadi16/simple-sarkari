import pytest
from crawlers.karnataka_dpar import KarnatakaDparAdapter

@pytest.mark.asyncio
@pytest.mark.skip(reason="KarnatakaDparAdapter is not fully implemented yet")
async def test_crawler():
    source = {
        "id": "karnataka_dpar",
        "seed_urls": ["https://dpar.karnataka.gov.in/page/Circulars/en"],
        "max_documents_per_run": 2
    }
    adapter = KarnatakaDparAdapter(source)
    
    candidates = await adapter.fetch_listing()
    
    assert candidates is not None
    assert len(candidates) > 0
    assert candidates[0].title is not None
