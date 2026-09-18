"""
Crawler service — orchestrates crawl runs using source-specific adapters.

Responsibilities:
  - Load source configuration
  - Resolve adapter class
  - Execute crawl run (listing → detail → storage)
  - Record crawl run results
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from models.source import CrawlRun


# Adapter registry — maps source adapter name → class
ADAPTER_REGISTRY: dict[str, type] = {}


def _load_adapters() -> None:
    """Lazy-load adapter classes to avoid circular imports."""
    from crawlers.pib import PibAdapter
    from crawlers.dopt import DoptAdapter
    from crawlers.egazette import EGazetteAdapter
    from crawlers.doe import DoeAdapter
    from crawlers.india_gov import IndiaGovAdapter
    from crawlers.karnataka_egazette import KarnatakaGazetteAdapter
    from crawlers.karnataka_dpar import KarnatakaDparAdapter
    from crawlers.karnataka_finance import KarnatakaFinanceAdapter
    from crawlers.karnataka_itbt import KarnatakaItbtAdapter

    ADAPTER_REGISTRY.update({
        "pib": PibAdapter,
        "dopt": DoptAdapter,
        "egazette": EGazetteAdapter,
        "doe": DoeAdapter,
        "india_gov": IndiaGovAdapter,
        "karnataka_egazette": KarnatakaGazetteAdapter,
        "karnataka_dpar": KarnatakaDparAdapter,
        "karnataka_finance": KarnatakaFinanceAdapter,
        "karnataka_itbt": KarnatakaItbtAdapter,
    })


def get_adapter(adapter_name: str, source_config: dict):
    """Get an instantiated adapter for the given source."""
    if not ADAPTER_REGISTRY:
        _load_adapters()
    adapter_cls = ADAPTER_REGISTRY.get(adapter_name)
    if adapter_cls is None:
        raise ValueError(f"Unknown adapter: {adapter_name}")
    return adapter_cls(source_config)


async def run_crawl(db: AsyncIOMotorDatabase, source_id: str, max_pages: int = 10, max_documents: int = 50) -> CrawlRun:
    """
    Execute a crawl run for the given source.

    TODO: Implement the full crawl pipeline:
      1. Fetch source config from DB
      2. Instantiate adapter
      3. Get listing URLs
      4. Fetch and parse listing pages
      5. Deduplicate discovered documents
      6. Fetch detail pages / PDFs
      7. Store raw content in S3
      8. Create circular records
      9. Queue AI processing jobs
      10. Return CrawlRun summary
    """
    raise NotImplementedError("run_crawl")
