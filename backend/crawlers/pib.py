"""
PIB (Press Information Bureau) adapter — pib.gov.in

Parses press release listings and detail pages.
"""

from crawlers.base import BaseCrawlerAdapter


class PibAdapter(BaseCrawlerAdapter):
    """Adapter for the Press Information Bureau."""

    async def get_listing_urls(self) -> list[str]:
        # TODO: Return seed URLs from source config
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        # TODO: Parse PIB listing page HTML
        # - Extract press release links from the listing table
        # - Return list of {"url": ..., "title": ..., "document_type": "press_release"}
        raise NotImplementedError("PibAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        # TODO: Parse individual press release page
        # - Extract title, body text, date, ministry/department
        # - Return structured dict
        raise NotImplementedError("PibAdapter.parse_detail_page")
