"""
DoPT (Department of Personnel & Training) adapter — dopt.gov.in
"""

from crawlers.base import BaseCrawlerAdapter


class DoptAdapter(BaseCrawlerAdapter):
    """Adapter for the Department of Personnel & Training."""

    async def get_listing_urls(self) -> list[str]:
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        # TODO: Parse DoPT orders/circulars listing
        raise NotImplementedError("DoptAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        # TODO: Parse DoPT detail page
        raise NotImplementedError("DoptAdapter.parse_detail_page")
