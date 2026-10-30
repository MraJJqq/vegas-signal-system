import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import publish_signal_manifest


class PublishSignalManifestTests(unittest.TestCase):
    def test_generates_whitelisted_formal_signals_without_bark_key(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            output = Path(directory) / "manifest.json"
            report.write_text(json.dumps({
                "finished_at_utc": "2026-10-30T02:00:00+00:00",
                "signals": [
                    {"formal_signal": True, "symbol": "NVDAUSDT"},
                    {"formal_signal": True, "symbol": "JPMUSDT"},
                    {"formal_signal": False, "symbol": "TSLAUSDT"},
                ],
            }), encoding="utf-8")
            with patch.dict(os.environ, {"V9_PUBLIC_SIGNAL_PATH": str(output)}, clear=True), \
                 patch.object(sys, "argv", ["publish_signal_manifest.py", str(report)]):
                self.assertEqual(publish_signal_manifest.main(), 0)
            state = json.loads(output.read_text(encoding="utf-8"))
            signals = state["__daily_formal_signals__"]["signals"]
            self.assertEqual([item["symbol"] for item in signals], ["NVDAUSDT"])
            self.assertNotIn("V9_BARK_KEY", os.environ)

    def test_missing_output_path_fails(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, "argv", ["publish_signal_manifest.py", "missing.json"]):
            self.assertEqual(publish_signal_manifest.main(), 2)

    def test_invalid_report_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            output = Path(directory) / "manifest.json"
            report.write_text("{invalid", encoding="utf-8")
            with patch.dict(os.environ, {"V9_PUBLIC_SIGNAL_PATH": str(output)}, clear=True), \
                 patch.object(sys, "argv", ["publish_signal_manifest.py", str(report)]):
                self.assertEqual(publish_signal_manifest.main(), 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
