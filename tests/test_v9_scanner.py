import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
import bitget_scanner


class V9ScannerIntegrityTests(unittest.TestCase):
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
