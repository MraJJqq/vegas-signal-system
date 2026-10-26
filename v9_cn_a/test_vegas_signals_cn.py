import unittest
from vegas_signals_cn import detect_formal_signals, ema

class VegasAshare1HTests(unittest.TestCase):
    def candles(self, count):
        return [
            {"timestamp_ms": i * 3_600_000, "open": 100.0, "high": 100.0,
             "low": 100.0, "close": 100.0, "closed": True}
            for i in range(count)
        ]

    def test_ema_requires_full_period(self):
        self.assertEqual(ema([1.0, 2.0], 3), [None, None])
        values = ema([100.0] * 676, 676)
        self.assertEqual(values[-1], 100.0)
        self.assertTrue(all(v is None for v in values[:-1]))

    def test_requires_676_closed_native_hourly_candles(self):
        with self.assertRaisesRegex(ValueError, "at least 676"):
            detect_formal_signals("SH600000", self.candles(675), {})

    def test_touch_then_later_ema12_close_confirms_once(self):
        candles = self.candles(676)
        state = {"timeframe": "4H", "observing": True, "last_processed_timestamp_ms": 0}
        first = detect_formal_signals("SH600000", candles, state)
        self.assertEqual(first, [])
        self.assertEqual(state["timeframe"], "1H")
        self.assertTrue(state["observing"])
        next_bar = {"timestamp_ms": 676 * 3_600_000, "open": 100.5, "high": 101.0,
                    "low": 100.5, "close": 101.0, "closed": True}
        signals = detect_formal_signals("SH600000", candles + [next_bar], state)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["filter_side"], "上方")
        self.assertTrue(signals[0]["formal_signal"])
        self.assertFalse(state["observing"])
        self.assertEqual(detect_formal_signals("SH600000", candles + [next_bar], state), [])

if __name__ == "__main__":
    unittest.main()
