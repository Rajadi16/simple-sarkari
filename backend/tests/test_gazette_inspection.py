"""Check the optional inspector's failure paths without opening a browser."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inspect_gazette as inspector
from crawlers.base import FetchResult


class InspectorTests(unittest.TestCase):
    def test_rejected_preflight_stops_before_browser_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            args = inspector.arguments(["egazette", "--output", directory])
            rejected = FetchResult(url="https://egazette.gov.in/", status_code=403,
                                   blocked=True, block_reason="403_forbidden")
            with patch.object(inspector, "preflight", new=AsyncMock(return_value=(rejected.url, rejected))), \
                    patch.dict(sys.modules, {"selenium": None}), contextlib.redirect_stdout(io.StringIO()):
                code = inspector.inspect(args)
            self.assertEqual(code, 1)
            report = json.loads((Path(directory)/"egazette.json").read_text())
            self.assertEqual(report["reason"], "403_forbidden")
            self.assertFalse(report["ingested"])

    def test_total_deadline_stops_child_once_and_reports_failure(self):
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("fixture", 10)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(inspector.subprocess, "Popen", return_value=process) as spawn, \
                patch.object(inspector, "stop_process_tree") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            code = inspector.main(["karnataka_egazette", "--output", directory, "--timeout", "10"])
            self.assertEqual(code, 1)
            spawn.assert_called_once()
            stop.assert_called_once_with(process)
            report = json.loads((Path(directory)/"karnataka_egazette.json").read_text())
            self.assertEqual(report["reason"], "inspection_timeout")

    def test_bad_source_and_unbounded_timeout_are_rejected(self):
        for argv in (["pib"], ["egazette", "--timeout", "inf"], ["egazette", "--timeout", "999"],
                     ["egazette", "--click-selector", "a"] + ["--click-selector", "b"]*3):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                inspector.arguments(argv)


if __name__ == "__main__":
    unittest.main()
