"""Exercise discovery and production crawl outcomes without live services."""

import asyncio
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawlers.base import FetchResult, _etag_cache
from crawlers.dopt import DoptAdapter
from crawlers.pib import PibAdapter
from crawlers.source_config import normalize_source_config, PIB_RSS_URL
from lib.security import validate_url
from models.circular import CanonicalCircular, Attachment
from services import crawler_service as service
import test_crawlers as diagnostics


class SourceTests(unittest.TestCase):
    def test_saved_policy_is_flattened_without_mutating_mongo_document(self):
        original = {"source_id": "dopt", "status": "active", "base_domains": ["dopt.gov.in"],
                    "seed_urls": ["https://www.dopt.gov.in/orders-circulars"],
                    "crawl_policy": {"max_documents_per_run": 2, "max_pages_per_run": 1}}
        snapshot = deepcopy(original)
        normalized = normalize_source_config(original)
        self.assertEqual(normalized["max_documents_per_run"], 2)
        self.assertEqual(normalized["seed_urls"], ["https://dopt.gov.in/"])
        self.assertIn("documents.doptcirculars.nic.in", normalized["base_domains"])
        self.assertNotIn("crawl_policy", normalized)
        self.assertEqual(original, snapshot)
        self.assertEqual(normalize_source_config(normalized), normalized)

    def test_custom_seed_and_paused_state_are_preserved(self):
        config = normalize_source_config({"source_id": "dopt", "status": "paused",
                                         "seed_urls": ["https://dopt.gov.in/custom"],
                                         "crawl_policy": {"enabled": True}})
        self.assertFalse(config["enabled"])
        self.assertEqual(config["seed_urls"], ["https://dopt.gov.in/custom"])

    def test_dopt_finds_official_external_pdf_with_query_and_rejects_navigation(self):
        # Minimal fixture matching link shapes observed at https://dopt.gov.in/.
        adapter = DoptAdapter({"source_id": "dopt"})
        html = '''<table><tr><td>18/09/2026</td><td>Official circular</td><td>
          <a href="https://documents.doptcirculars.nic.in/D2/test.PDF?download=1">PDF</a>
          </td></tr><tr><td><a href="https://example.com/fake.pdf">Unrelated</a></td></tr>
          <tr><td><a href="/orders">Orders navigation</a></td></tr></table>
          <a href="https://documents.doptcirculars.nic.in/D2/test.PDF?download=1">Duplicate</a>'''
        candidates = adapter._parse_listing_html(html, "https://dopt.gov.in/")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Official circular")
        self.assertEqual(candidates[0].published_date_text, "18/09/2026")
        self.assertEqual(candidates[0].document_url, candidates[0].detail_url)
        validate_url(candidates[0].detail_url)
        with self.assertRaises(ValueError):
            validate_url("https://documents.doptcirculars.nic.in.example.com/fake.pdf")

    def test_rss_discovery_keeps_provenance_without_promoting_summary(self):
        adapter = PibAdapter(diagnostics.ADAPTERS["pib"]["source"])
        body = b'''<?xml version="1.0"?><rss version="2.0"><channel>
          <item><title>Official release</title><link>https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=123</link>
          <pubDate>Fri, 18 Sep 2026 12:00:00 GMT</pubDate><description>Summary only</description></item>
          <item><link>https://example.com/PressReleaseDetail.aspx?PRID=124</link></item>
          <item><link>https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=123</link></item>
          </channel></rss>'''
        result = adapter._parse_listing_rss(body, PIB_RSS_URL)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_reference_id, "PRID=123")
        self.assertEqual(result[0].discovered_from_url, PIB_RSS_URL)
        self.assertNotIn("Summary only", str(result[0].model_dump()))
        with self.assertRaises(ValueError):
            adapter._parse_listing_rss(b"<html><body>Not RSS</body></html>", PIB_RSS_URL)


def circular_for(candidate, body="Extracted official document"):
    return CanonicalCircular(
        source={"source_id": "pib", "source_name": "PIB", "source_domain": "www.pib.gov.in",
                "source_url": candidate.detail_url, "official_document_url": candidate.detail_url},
        classification={"government_level": "central", "department": "Ministry"},
        identity={"title_original": candidate.title or "Official document"},
        content={"original_text": body}, provenance={},
    )


class ProductionAdapter(PibAdapter):
    def __init__(self, config, handler):
        super().__init__(config)
        self.handler = handler
        self.closed = False
        self.parse = AsyncMock(side_effect=lambda candidate, result: circular_for(candidate))

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return self._client

    async def close(self):
        self.closed = True
        await super().close()


class ProductionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _etag_cache.clear()
        self.source = deepcopy(diagnostics.ADAPTERS["pib"]["source"])
        for key in ("max_pages_per_run", "max_documents_per_run", "request_delay_seconds", "respect_robots"):
            self.source.pop(key, None)
        self.source["crawl_policy"] = {"max_pages_per_run": 1, "max_documents_per_run": 2,
                                       "request_delay_seconds": 0, "respect_robots": False}
        self.source["status"] = "active"
        self.db = NS(sources=NS(find_one=AsyncMock(side_effect=lambda _: deepcopy(self.source))),
                     crawl_runs=NS(insert_one=AsyncMock(), update_one=AsyncMock()),
                     circulars=NS(find_one=AsyncMock(return_value=None)))
        self.requests = []
        self.saved = []
        self.adapter = None
        self.handler = self.success
        self.budget = 1
        self.patches = [
            patch.object(service, "get_adapter", side_effect=self.make_adapter),
            patch.object(service, "get_settings", side_effect=lambda: NS(crawler_run_timeout_seconds=self.budget)),
            patch.object(service, "save_circular", new=AsyncMock(side_effect=lambda db, circular: self.saved.append(circular))),
            patch.object(service, "log_ingestion_event", new=AsyncMock()),
            patch.object(service, "is_duplicate", new=AsyncMock(return_value=False)),
            patch.object(service, "store_raw", new=AsyncMock(side_effect=lambda id, body, ext: (f"raw/{id}/original.{ext}", False))),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_adapter(self, name, config):
        self.adapter = ProductionAdapter(config, self.dispatch)
        return self.adapter

    async def dispatch(self, request):
        self.requests.append(request)
        result = self.handler(request)
        return await result if asyncio.iscoroutine(result) else result

    def success(self, request):
        if "Allrel.aspx" in request.url.path:
            links = ''.join(f'<a href="/PressReleaseDetail.aspx?PRID={n}">Release {n}</a>' for n in range(3))
            return httpx.Response(200, text=links)
        return httpx.Response(200, text="<p>Official document</p>")

    async def run_crawl(self):
        return await service.run_crawl(self.db, "pib", max_pages=5, max_documents=50)

    async def test_success_respects_saved_limits_and_closes(self):
        self.source["seed_urls"].append("https://www.pib.gov.in/Allrel.aspx?second=1")
        result = await self.run_crawl()
        self.assertEqual(result.status, "completed", result.errors)
        self.assertEqual(result.documents_new, 2)
        self.assertEqual(result.pages_fetched, 1)
        self.assertEqual(len(self.requests), 3)
        self.assertTrue(self.adapter.closed)
        self.assertEqual(self.db.crawl_runs.update_one.call_args.args[1]["$set"]["status"], "completed")

    async def test_rejected_listing_is_terminal_and_never_parsed(self):
        for code in (403, 429, 404, 500):
            with self.subTest(code=code):
                self.requests.clear()
                self.handler = lambda _: httpx.Response(code)
                result = await self.run_crawl()
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.errors[0]["http_status"], code)
                self.assertEqual(result.blocked_requests, 1)
                self.assertEqual(len(self.requests), 1)
                self.adapter.parse.assert_not_awaited()
                self.assertTrue(self.adapter.closed)

    async def test_html_waf_page_is_not_successful_empty_listing(self):
        self.handler = lambda _: httpx.Response(200, text="<html><title>Request Rejected</title></html>")
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.errors[0]["reason"], "waf_block")

    async def test_zero_links_and_304_are_distinct(self):
        self.handler = lambda _: httpx.Response(200, text="<html>No links</html>")
        result = await self.run_crawl()
        self.assertEqual(result.errors[0]["reason"], "no_document_links")
        self.handler = lambda _: httpx.Response(304)
        result = await self.run_crawl()
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.errors, [])

    async def test_detail_rejection_stops_after_first_document(self):
        self.handler = lambda request: self.success(request) if "Allrel" in request.url.path else httpx.Response(403)
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.saved), 1)
        self.assertEqual(self.saved[0].processing.status, "manual_review_required")
        self.assertEqual(result.errors[0]["stage"], "detail")

    async def test_deadline_and_transport_failure_preserve_reason(self):
        async def hanging(_):
            await asyncio.Event().wait()
        self.handler = hanging
        self.budget = 0.01
        result = await self.run_crawl()
        self.assertEqual(result.errors[0]["reason"], "crawl_timeout")
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.adapter.closed)
        self.budget = 1
        def fail(request):
            raise httpx.ConnectError("certificate hostname mismatch", request=request)
        self.handler = fail
        result = await self.run_crawl()
        self.assertIn("hostname mismatch", result.errors[0]["error_detail"])
        self.assertEqual(result.pages_fetched, 0)

    async def test_partial_progress_survives_later_failure(self):
        def response(request):
            return httpx.Response(403) if str(request.url).endswith("PRID=1") else self.success(request)
        self.handler = response
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.documents_new, 1)
        self.assertEqual(result.blocked_requests, 1)

    async def test_paused_source_never_fetches(self):
        self.source["status"] = "paused"
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertEqual(self.requests, [])
        self.assertIsNone(self.adapter)

    async def test_pdf_capture_is_stored_once_and_not_as_html(self):
        candidate = NS(detail_url="https://dopt.gov.in/example.pdf", title="Official PDF")
        circular = circular_for(candidate)
        circular.attachments = [Attachment(url=candidate.detail_url, type="pdf")]
        result = FetchResult(url=candidate.detail_url, status_code=200, body=b"%PDF-1.7 fixture", content_type="application/pdf")
        await service._store_primary_capture(circular, result)
        self.assertIsNone(circular.provenance.raw_html_s3_key)
        self.assertTrue(circular.provenance.raw_pdf_s3_key.endswith(".pdf"))
        self.assertEqual(circular.attachments[0].s3_key, circular.provenance.raw_pdf_s3_key)
        service.store_raw.assert_awaited_once()

    async def test_failed_extraction_requires_manual_review(self):
        circular = circular_for(NS(detail_url="https://dopt.gov.in/test.pdf", title="Test"), " ")
        service._require_extracted_text(circular)
        self.assertEqual(circular.processing.status, "manual_review_required")

    async def test_unknown_source_cannot_silently_ingest_as_pib(self):
        self.source = None
        with self.assertRaisesRegex(ValueError, "not found"):
            await service.ingest_single_url(self.db, "https://dopt.gov.in/test.pdf", "dopt")
        self.assertIsNone(self.adapter)

    async def test_manual_url_storage_error_closes_adapter(self):
        service.store_raw.side_effect = OSError("storage unavailable")
        with self.assertRaisesRegex(OSError, "storage unavailable"):
            await service.ingest_single_url(self.db, "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1", "pib")
        self.assertTrue(self.adapter.closed)

    async def test_failed_run_does_not_cache_away_its_listing_on_explicit_retry(self):
        def response(request):
            if "Allrel" in request.url.path:
                if request.headers.get("if-none-match"):
                    return httpx.Response(304)
                return httpx.Response(200, headers={"etag": "v1"},
                                     text='<a href="/PressReleaseDetail.aspx?PRID=1">Release</a>')
            return httpx.Response(403)
        self.handler = response
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertNotIn(self.source["seed_urls"][0], _etag_cache)
        result = await self.run_crawl()
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(self.requests), 4)


if __name__ == "__main__":
    unittest.main()
