import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import ntfy_notifier


EXPECTED_CORE = ["BTC", "HYPE", "XAU", "CL"]
EXPECTED_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC", "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK", "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX"
]
EXPECTED_POOL = set(EXPECTED_CORE + EXPECTED_STOCKS)


class V9NotifierTests(unittest.TestCase):
    def test_empty_report_has_both_nochange_groups(self):
        body, symbols = ntfy_notifier.build_body({"signals": []})
        self.assertEqual(symbols, [])
        self.assertIn("🔸 美股巨头\n▰ No change ▰", body)
        self.assertIn("🔸 核心能源\n▰ No change ▰", body)

    def test_symbols_are_deduplicated_and_grouped(self):
        body, symbols = ntfy_notifier.build_body({"signals": [
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": True, "symbol": "BTCUSDT"},
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": False, "symbol": "TSLAUSDT"},
        ]})
        self.assertEqual(symbols, ["NVDA", "BTC"])
        self.assertIn("▰ NVDA ▰", body)
        self.assertIn("▰ BTC ▰", body)
        self.assertNotIn("▰ TSLA ▰", body)
        self.assertNotIn("▰ No change ▰", body)

    def test_all_27_current_pool_symbols_are_allowed(self):
        body, symbols = ntfy_notifier.build_body({
            "signals": [{"formal_signal": True, "symbol": f"{symbol}USDT"}
                        for symbol in EXPECTED_STOCKS + EXPECTED_CORE]
        })
        self.assertEqual(set(symbols), EXPECTED_POOL)
        self.assertEqual(len(symbols), 27)
        for symbol in EXPECTED_POOL:
            self.assertIn(f"▰ {symbol} ▰", body)
        self.assertNotIn("JPM", body)

    def test_stale_symbols_outside_current_pool_are_ignored(self):
        body, symbols = ntfy_notifier.build_body({"signals": [
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": True, "symbol": "CVXUSDT"},
            {"formal_signal": True, "symbol": "CRCLUSDT"},
            {"formal_signal": True, "symbol": "MSTRUSDT"},
            {"formal_signal": True, "symbol": "SNDKUSDT"},
        ]})
        self.assertEqual(set(symbols), {"NVDA", "SNDK"})
        self.assertIn("🔸 美股巨头", body)
        self.assertIn("🔸 核心能源", body)
        self.assertIn("▰ NVDA ▰", body)
        self.assertIn("▰ SNDK ▰", body)
        self.assertNotIn("🔔", body)
        for stale in ("CVX", "CRCL", "MSTR"):
            self.assertNotIn(f"▰ {stale} ▰", body)

    def test_send_empty_report_posts_to_bark(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            with patch.dict(os.environ, {"V9_BARK_KEY": "test-key"}, clear=False), patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                self.assertEqual(ntfy_notifier.send_notification(str(path)), 0)
                self.assertEqual(urlopen.call_count, 1)
                payload = json.loads(urlopen.call_args.args[0].data.decode())
                self.assertIn("🔸 美股巨头\n▰ No change ▰", payload["body"])
                self.assertIn("🔸 核心能源\n▰ No change ▰", payload["body"])
                self.assertNotIn("🔔", payload["body"])
                self.assertNotIn("VEGAS V9 SIGNAL SYSTEM", payload["body"])
                self.assertEqual(payload["title"], "VEGAS V9 SIGNAL SYSTEM")

    def test_missing_report_fails_cleanly(self):
        with patch.dict(os.environ, {"V9_BARK_KEY": "test-key"}, clear=False):
            self.assertEqual(ntfy_notifier.send_notification("/path/that/does/not/exist.json"), 1)


if __name__ == "__main__":
    unittest.main()
