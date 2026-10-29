import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import bitget_scanner


class V9ScannerIntegrityTests(unittest.TestCase):

    def test_http_429_is_retried_and_then_succeeds(self):
        rate_limited = urllib.error.HTTPError(
            "https://api.bitget.com/test", 429, "Too Many Requests",
            {"Retry-After": "0"}, None
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"code":"00000","data":[]}'
        with patch.object(bitget_scanner, "_wait_for_request_slot"), \
             patch.object(bitget_scanner.time, "sleep"), \
             patch.object(bitget_scanner.urllib.request, "urlopen", side_effect=[rate_limited, response]) as request:
            payload = bitget_scanner.get_json("/test", {})
        self.assertEqual(payload["code"], "00000")
        self.assertEqual(request.call_count, 2)

    def test_rate_limit_wait_happens_outside_lock(self):
        class TrackingLock:
            held = False

            def __enter__(self):
                self.held = True

            def __exit__(self, exc_type, exc_value, traceback):
                self.held = False

        lock = TrackingLock()
        with patch.object(bitget_scanner, "_rate_limit_lock", lock), \\
             patch.object(bitget_scanner.time, "monotonic", return_value=100.0), \\
             patch.object(bitget_scanner.time, "sleep") as sleep:
            bitget_scanner._next_request_at = 101.0

            def assert_unlocked(delay):
                self.assertFalse(lock.held)
                self.assertEqual(delay, 1.0)

            sleep.side_effect = assert_unlocked
            bitget_scanner._wait_for_request_slot()

        self.assertEqual(bitget_scanner._next_request_at, 101.0 + bitget_scanner.MIN_REQUEST_INTERVAL_SECONDS)
        sleep.assert_called_once_with(1.0)

    def test_partial_scan_is_not_success(self):
        report = {
            "scan_status": "partial",
            "symbols_ok": 26,
            "symbols_total": 27,
            "symbols_excluded": 1,
        }
        self.assertEqual(bitget_scanner.scan_exit_code(report), 1)

    def test_complete_scan_is_success(self):
        report = {
            "scan_status": "complete",
            "symbols_ok": 27,
            "symbols_total": 27,
            "symbols_excluded": 0,
        }
        self.assertEqual(bitget_scanner.scan_exit_code(report), 0)

    def test_zero_success_scan_is_not_success(self):
        report = {
            "scan_status": "failed",
            "symbols_ok": 0,
            "symbols_total": 27,
            "symbols_excluded": 27,
        }
        self.assertEqual(bitget_scanner.scan_exit_code(report), 1)

    def test_insufficient_ema_warmup_is_warning_when_all_symbols_scanned(self):
        report = {
            "scan_status": "complete_with_warmup_warning",
            "symbols_ok": 27,
            "symbols_total": 27,
            "symbols_excluded": 0,
            "symbols_warmup_insufficient": 1,
        }
        self.assertEqual(bitget_scanner.scan_exit_code(report), 0)

    def test_duplicate_candle_timestamp_is_rejected(self):
        duplicate_rows = [
            [5000, "10", "11", "9", "10"],
            [5000, "10", "11", "9", "10"],
        ]
        with patch.object(bitget_scanner, "EMA_HISTORY_LIMIT", 2), \
             patch.object(bitget_scanner, "HISTORY_CANDLE_PAGE_LIMIT", 2), \
             patch.object(bitget_scanner, "get_json", return_value={"code": "00000", "data": duplicate_rows}):
            with self.assertRaisesRegex(bitget_scanner.BitgetError, "Duplicate candle timestamp"):
                bitget_scanner.fetch_candles("TESTUSDT", "4H")

    def test_4h_candles_are_paginated_and_returned_oldest_first(self):
        pages = [
            [[5000, "10", "11", "9", "10"], [4000, "10", "11", "9", "10"]],
            [[3000, "10", "11", "9", "10"], [2000, "10", "11", "9", "10"]],
            [[1000, "10", "11", "9", "10"]],
        ]
        calls = []

        def fake_get_json(path, params):
            calls.append((path, dict(params)))
            return {"code": "00000", "data": pages[len(calls) - 1]}

        with patch.object(bitget_scanner, "EMA_HISTORY_LIMIT", 5), \
             patch.object(bitget_scanner, "HISTORY_CANDLE_PAGE_LIMIT", 2), \
             patch.object(bitget_scanner, "get_json", side_effect=fake_get_json):
            candles = bitget_scanner.fetch_candles("TESTUSDT", "4H")

        self.assertEqual([c["timestamp_ms"] for c in candles], [1000, 2000, 3000, 4000, 5000])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(path == "/api/v2/mix/market/history-candles" for path, _ in calls))
        self.assertEqual(calls[1][1]["endTime"], "3999")
        self.assertEqual(calls[2][1]["endTime"], "1999")


if __name__ == "__main__":
    unittest.main()
