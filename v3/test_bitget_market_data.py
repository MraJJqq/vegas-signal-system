"""Offline tests for the V3 Bitget market-data adapter."""
import unittest
from urllib.parse import parse_qs, urlparse

from bitget_market_data import (
    FOUR_HOURS_MS,
    BitgetAPIError,
    MarketCandle,
    build_v3_inputs,
    ema,
    fetch_closed_4h_candles,
    fetch_v3_inputs,
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
                    ["0", "100", "101", "99", "100", "1", "10"],
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

    def test_ema_requires_full_warmup_and_uses_sma_seed(self):
        self.assertEqual(ema([1, 2, 3], 4), [None, None, None])
        result = ema([1, 2, 3, 4], 3)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], 2.0)
        self.assertAlmostEqual(result[3], 3.0)

    def test_v3_inputs_wait_until_ema676_exists(self):
        bars = [
            candle(i * FOUR_HOURS_MS, 100 + i, 101 + i, 99 + i, 100 + i)
            for i in range(700)
        ]
        result = build_v3_inputs(bars)
        self.assertEqual(len(result), 700 - 675)
        self.assertEqual(result[0].timestamp_ms, 675 * FOUR_HOURS_MS)
        self.assertTrue(result[0].candle.closed)
        self.assertGreater(result[0].ema576, 0)
        self.assertGreater(result[0].ema676, 0)

    def test_fetch_v3_inputs_rejects_8h_and_2h(self):
        for timeframe in ("8H", "2H", "1H"):
            with self.subTest(timeframe=timeframe):
                with self.assertRaises(ValueError):
                    fetch_v3_inputs("BTCUSDT", timeframe=timeframe)


if __name__ == "__main__":
    unittest.main()
