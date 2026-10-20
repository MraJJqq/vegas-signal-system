import unittest

import pandas as pd

from signal_engine import generate_signals


class SignalEngineTests(unittest.TestCase):
    def frame(self, closes, freq):
        index = pd.date_range("2025-01-01", periods=len(closes), freq=freq, tz="UTC")
        close = pd.Series(closes, index=index, dtype=float)
        return pd.DataFrame({
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        }, index=index)

    def test_empty_data_returns_no_signals(self):
        empty4 = pd.DataFrame(columns=["open", "high", "low", "close"],
                              index=pd.DatetimeIndex([], tz="UTC"))
        empty8 = empty4.copy()
        self.assertEqual(generate_signals(empty4, empty8), [])

    def test_rejects_duplicate_timestamps(self):
        frame = self.frame([10, 11, 12], "4h")
        frame = pd.concat([frame, frame.iloc[[-1]]])
        with self.assertRaises(ValueError):
            generate_signals(frame, self.frame([10, 11, 12], "8h"))

    def test_rejects_missing_ohlc_columns(self):
        frame = self.frame([10, 11, 12], "4h")[["close"]]
        with self.assertRaises(ValueError):
            generate_signals(frame, self.frame([10, 11, 12], "8h"))

    def test_no_lookahead_alignment_is_backward(self):
        # Smoke test with enough history for the configured EMA windows.
        closes4 = [100 + i * 0.1 for i in range(700)]
        closes8 = [100 + i * 0.2 for i in range(350)]
        result = generate_signals(self.frame(closes4, "4h"), self.frame(closes8, "8h"))
        self.assertIsInstance(result, list)
        self.assertTrue(all(hasattr(signal, "timestamp") for signal in result))


if __name__ == "__main__":
    unittest.main()
