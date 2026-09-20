"""Offline regression tests: no government requests, MongoDB, or AWS calls."""

import asyncio
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_crawlers as diagnostics
from crawlers.base import _etag_cache
from crawlers.pib import PibAdapter


def valid_circular():
    return NS(
        id="fixture",
        source=NS(source_id="pib", source_name="PIB",
                  source_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=123",
                  official_document_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=123"),
        identity=NS(title_original="Official release"),
        classification=NS(government_level="central", department="Department",
                          document_type="press_release", language="en-IN"),
        provenance=NS(retrieved_at="2026-09-18", content_hash="sha256:fixture"),
        processing=NS(status="extracted", published=False),
        content=NS(original_text="A real extracted document body."),
    )


class FixtureAdapter(PibAdapter):
    def __init__(self, config, handler):
        super().__init__(config)
        self.handler = handler
        self.circular = valid_circular()
        self.closed = False
        self.parse_calls = 0

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return self._client

    async def parse(self, candidate, result):
        self.parse_calls += 1
        return self.circular

    async def close(self):
        self.closed = True
        await super().close()


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _etag_cache.clear()
        self.config = {
            "class": "fixture.Adapter",
            # All requests use MockTransport; robots fetching is outside these tests.
            "source": dict(diagnostics.ADAPTERS["pib"]["source"],
                           respect_robots=False, request_delay_seconds=0),
        }
        self.requests = []
        self.adapter = FixtureAdapter(self.config["source"], self.handler)

    def handler(self, request):
        self.requests.append(request)
        if "Allrel.aspx" in request.url.path:
            if request.headers.get("if-none-match"):
                return httpx.Response(304)
            return httpx.Response(
                200, headers={"etag": "fixture-v1", "content-type": "text/html"},
                text='<a href="/PressReleaseDetail.aspx?PRID=123">Official release</a>',
            )
        return httpx.Response(200, text="<p>Official release body</p>")

    async def diagnose(self, timeout=1):
        with patch.object(diagnostics, "_import_class", return_value=lambda _: self.adapter):
            return await diagnostics.test_adapter("pib", self.config, timeout_seconds=timeout)

    async def test_etag_listing_is_fetched_once_and_parsed(self):
        result = await self.diagnose()
        listing_requests = [r for r in self.requests if "Allrel.aspx" in r.url.path]
        self.assertEqual(len(listing_requests), 1)
        self.assertEqual(result["candidates_found"], 1)
        self.assertTrue(result["parse_ok"], result)
        self.assertTrue(self.adapter.closed)

    async def test_missing_required_field_is_failure(self):
        self.adapter.circular.source.source_name = ""
        result = await self.diagnose()
        self.assertFalse(result["parse_ok"])
        self.assertIn("source.source_name", result["required_fields_failed"])

    async def test_empty_extracted_text_is_failure(self):
        self.adapter.circular.content.original_text = "  "
        result = await self.diagnose()
        self.assertFalse(result["parse_ok"])
        self.assertIn("content.original_text", result["required_fields_failed"])

    async def test_http_error_is_not_reported_as_zero_links(self):
        self.adapter.handler = lambda _: httpx.Response(404, text="Not found")
        result = await self.diagnose()
        self.assertIn("HTTP 404", result["error"])
        self.assertFalse(result["listing_reachable"])
        self.assertEqual(self.adapter.parse_calls, 0)

    async def test_unchanged_listing_is_not_reported_as_parser_failure(self):
        self.adapter.handler = lambda _: httpx.Response(304)
        result = await self.diagnose()
        self.assertTrue(result["listing_not_modified"])
        self.assertIn("unchanged", result["error"])
        self.assertEqual(self.adapter.parse_calls, 0)

    async def test_empty_listing_body_is_reported(self):
        self.adapter.handler = lambda _: httpx.Response(200)
        result = await self.diagnose()
        self.assertIn("empty body", result["error"])
        self.assertFalse(result["parse_ok"])

    async def test_deadline_cancels_fetch_and_closes_adapter(self):
        async def hanging_fetch(_):
            await asyncio.Event().wait()
        self.adapter.fetch = hanging_fetch
        result = await self.diagnose(timeout=0.01)
        self.assertTrue(result["timed_out"])
        self.assertTrue(self.adapter.closed)
        self.assertFalse(result["parse_ok"])

    async def test_rejections_stop_without_retry(self):
        for status in (403, 429):
            with self.subTest(status=status):
                calls = []
                def reject(request):
                    calls.append(request)
                    return httpx.Response(status)
                self.adapter = FixtureAdapter(self.config["source"], reject)
                result = await self.diagnose()
                self.assertEqual(len(calls), 1)
                self.assertTrue(result["listing_blocked"])
                self.assertEqual(result["listing_http_status"], status)

    async def test_connect_and_timeout_errors_are_not_retried(self):
        for error_type in (httpx.ConnectError, httpx.ReadTimeout):
            with self.subTest(error_type=error_type):
                calls = []
                def fail(request):
                    calls.append(request)
                    raise error_type("fixture transport failure", request=request)
                self.adapter = FixtureAdapter(self.config["source"], fail)
                result = await self.diagnose()
                self.assertEqual(len(calls), 1)
                self.assertIn(error_type.__name__, result["error"])

    async def test_stale_connection_retries_once_then_succeeds(self):
        calls = []
        def recover(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError("closed connection", request=request)
            return httpx.Response(200, text="body")
        self.adapter.handler = recover
        try:
            fetched = await self.adapter.fetch(self.config["source"]["seed_urls"][0])
            self.assertFalse(fetched.blocked)
            self.assertEqual(len(calls), 2)
        finally:
            await self.adapter.close()

    async def test_persistent_protocol_error_stops_after_one_retry(self):
        calls = []
        def fail(request):
            calls.append(request)
            raise httpx.RemoteProtocolError("closed connection", request=request)
        self.adapter.handler = fail
        result = await self.diagnose()
        self.assertEqual(len(calls), 2)
        self.assertIn("RemoteProtocolError", result["error"])


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_or_misspelled_source_does_not_run_all(self):
        for argv in ([], ["piib"], ["pib", "--timeout", "0"],
                     ["pib", "--timeout", "nan"], ["pib", "--timeout", "inf"]):
            with self.subTest(argv=argv), patch.object(diagnostics, "test_adapter") as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    await diagnostics.main(argv)
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    async def test_json_output_and_exit_code_reflect_result(self):
        for passed in (True, False):
            result = {"name": "pib", "parse_ok": passed}
            with self.subTest(passed=passed):
                with patch.object(diagnostics, "test_adapter", new=AsyncMock(return_value=result)) as run:
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        code = await diagnostics.main(["pib", "--json", "--timeout", "10"])
                    self.assertEqual(code, 0 if passed else 1)
                    self.assertEqual(json.loads(output.getvalue()), [result])
                    run.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
