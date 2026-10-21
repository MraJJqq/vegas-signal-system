"""Offline tests for the V3 Bitget market-data adapter."""
import unittest
from urllib.parse import parse_qs, urlparse

from bitget_market_data import (
    FOUR_HOURS_MS,
    EIGHT_HOURS_MS,
    BitgetAPIError,
    MarketCandle,
    aggregate_8h_from_4h,
    build_v3_inputs,
    ema,
    fetch_closed_4h_candles,
    parse_candle_rows,
)


def candle(ts, open_price=100, high=105, low=95, close=102, volume=1):
    return MarketCandle(ts, open_price, high, low, close, volume, volume * 10)


class BitgetMarketDataTests(unittest.TestCase):
    def test_parse_rows_sorts_and_deduplicates(self):
        rows = [
            ["14400000", "100", "105", "95", "102", "1", "10"],
            ["0", "90", "101", "89", "100", "2", "20"],
            ["0", "91", "102", "90", "101", "3", "30"],
        ]
        result = parse_candle_rows(rows)
        self.assertEqual([c.timestamp_ms for c in result], [0, 14400000])
        self.assertEqual(result[0].close, 101.0)

    def test_rejects_bad_ohlc(self):
        with self.assertRaises(BitgetAPIError):
            parse_candle_rows([["0", "100", "99", "95", "101", "1", "10"]])

    def test_fetch_requests_bitget_4h_and_excludes_open_candle(self):
        now = 3 * FOUR_HOURS_MS + 1000
        captured = {}

        def fake_request(url):
            captured["url"] = url
            return {
                "code": "00000",
                "data": [
                    [str(0), "100", "101", "99", "100", "1", "10"],
                    [str(FOUR_HOURS_MS), "100", "102", "99", "101", "1", "10"],
                    [str(2 * FOUR_HOURS_MS), "101", "103", "100", "102", "1", "10"],
                    [str(3 * FOUR_HOURS_MS), "102", "104", "101", "103", "1", "10"],
                ],
            }

        result = fetch_closed_4h_candles(
            "btcusdt", limit=10, now_ms=now, request_json=fake_request
        )
        query = parse_qs(urlparse(captured["url"]).query)
        self.assertEqual(query["symbol"], ["BTCUSDT"])
        self.assertEqual(query["productType"], ["USDT-FUTURES"])
        self.assertEqual(query["granularity"], ["4H"])
        self.assertEqual([c.timestamp_ms for c in result],
                         [0, FOUR_HOURS_MS, 2 * FOUR_HOURS_MS])

    def test_8h_aggregation_requires_two_aligned_consecutive_4h_bars(self):
        bars = [
            candle(0, 100, 104, 98, 102),
            candle(FOUR_HOURS_MS, 102, 108, 101, 107),
            candle(2 * FOUR_HOURS_MS, 107, 109, 105, 106),
            # Missing the 12h bar means the next bucket is not aggregated.
            candle(4 * FOUR_HOURS_MS, 106, 110, 104, 109),
        ]
        result = aggregate_8h_from_4h(bars)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].timestamp_ms, 0)
        self.assertEqual(result[0].open, 100)
        self.assertEqual(result[0].high, 108)
        self.assertEqual(result[0].low, 98)
        self.assertEqual(result[0].close, 107)

    def test_ema_requires_full_warmup_and_uses_sma_seed(self):
        self.assertEqual(ema([1, 2, 3], 4), [None, None, None])
        result = ema([1, 2, 3, 4], 3)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], 2.0)
        self.assertAlmostEqual(result[3], 3.0)

    def test_v3_inputs_wait_until_ema169_exists(self):
        bars = [
            candle(i * FOUR_HOURS_MS, 100 + i, 101 + i, 99 + i, 100 + i)
            for i in range(180)
        ]
        result = build_v3_inputs(bars)
        self.assertEqual(len(result), 180 - 168)
        self.assertEqual(result[0].timestamp_ms, 168 * FOUR_HOURS_MS)
        self.assertTrue(result[0].candle.closed)

    def test_8h_interval_constant_is_eight_hours(self):
        self.assertEqual(EIGHT_HOURS_MS, 2 * FOUR_HOURS_MS)


if __name__ == "__main__":
    unittest.main()
