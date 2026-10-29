import json, os, sys, tempfile, unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import ntfy_notifier
import bitget_scanner
from market_config import CORE_MARKETS, STOCKS as STOCK_SYMBOLS

CORE = list(CORE_MARKETS)
STOCKS = list(STOCK_SYMBOLS)


class BarkNotifierTests(unittest.TestCase):
    def test_empty_report_has_both_no_change_groups(self):
        body, symbols = ntfy_notifier.build_body({"signals": []})
        self.assertEqual(symbols, [])
        self.assertEqual(body, "🔸 美股巨头\n▰ No change ▰\n\n🔸 核心能源\n▰ No change ▰")

    def test_formal_signals_deduplicated_and_non_formal_ignored(self):
        body, symbols = ntfy_notifier.build_body({"signals": [
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": True, "symbol": "BTCUSDT"},
            {"formal_signal": True, "symbol": "NVDAUSDT"},
            {"formal_signal": False, "symbol": "TSLAUSDT"}]})
        self.assertEqual(symbols, ["NVDA", "BTC"])
        self.assertNotIn("▰ TSLA ▰", body)

    def test_only_fixed_pool_symbols_are_rendered(self):
        _, symbols = ntfy_notifier.build_body(
            {"signals": [{"formal_signal": True, "symbol": f"{s}USDT"} for s in CORE + STOCKS]
             + [{"formal_signal": True, "symbol": "JPMUSDT"}]})
        self.assertEqual(set(symbols), set(CORE + STOCKS))
        self.assertEqual(len(symbols), 27)

    def test_payload_has_no_title_or_url_and_posts_once(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            path.write_text(json.dumps({"signals": []}), encoding="utf-8")
            with patch.dict(os.environ, {"V9_BARK_KEY": "test-key"}, clear=False), \
                 patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b'{"code":200}'
                self.assertEqual(ntfy_notifier.send_notification(str(path)), 0)
                payload = json.loads(urlopen.call_args.args[0].data.decode())
                self.assertNotIn("title", payload)
                self.assertNotIn("url", payload)
                self.assertEqual(payload["device_key"], "test-key")
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_retries_transient_network_failure_then_succeeds(self):
        with patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen, \
             patch.object(ntfy_notifier.time, "sleep") as sleep:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"code":200}'
            urlopen.side_effect = [urllib.error.URLError("temporary"), urlopen.return_value]
            ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(1)

    def test_retries_server_error_but_stops_after_three_attempts(self):
        error = urllib.error.HTTPError(
            ntfy_notifier.BARK_ENDPOINT, 503, "Unavailable", {}, None
        )
        with patch.object(ntfy_notifier.urllib.request, "urlopen", side_effect=error) as urlopen, \
             patch.object(ntfy_notifier.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "Bark HTTP 503"):
                ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})
            self.assertEqual(urlopen.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_rejects_bark_application_error(self):
        with patch.object(ntfy_notifier.urllib.request, "urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"code":400,"message":"bad request"}'
            with self.assertRaisesRegex(RuntimeError, "code=400"):
                ntfy_notifier.post_bark({"device_key": "test-key", "body": "test"})

    def test_oil_symbol_alias(self):
        self.assertEqual(ntfy_notifier.display_symbol("CLUSDT"), "CL")

    def test_scanner_and_notifier_share_the_same_market_pool(self):
        self.assertEqual(set(bitget_scanner.SYMBOLS), {f"{s}USDT" for s in CORE + STOCKS})
        self.assertEqual(ntfy_notifier.ALLOWED_SYMBOLS, set(CORE + STOCKS))
        self.assertEqual(len(bitget_scanner.SYMBOLS), 27)


if __name__ == "__main__":
    unittest.main()
