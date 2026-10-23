import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v8"))
from vegas_signals import detect_formal_signals


def candle(ts, close=100.0, high=100.0, low=100.0):
    return {
        "timestamp_ms": ts, "open": close, "high": high, "low": low,
        "close": close, "closed": True,
    }


class SignalStateTests(unittest.TestCase):
    def test_observation_persists_and_new_candle_confirms_once(self):
        state = {}
        initial = [candle(i * 3_600_000) for i in range(700)]
        self.assertEqual(detect_formal_signals("TESTUSDT", initial, state), [])
        self.assertTrue(state["observing"])
        self.assertEqual(state["last_processed_timestamp_ms"], initial[-1]["timestamp_ms"])

        expanded = initial + [candle(700 * 3_600_000, close=101.0, high=101.0, low=100.0)]
        signals = detect_formal_signals("TESTUSDT", expanded, state)
        self.assertEqual(len(signals), 1)
        self.assertTrue(signals[0]["formal_signal"])
        self.assertEqual(signals[0]["filter_side"], "上方")
        self.assertEqual(signals[0]["candle_timestamp_ms"], expanded[-1]["timestamp_ms"])
        self.assertFalse(state["observing"])
        self.assertEqual(detect_formal_signals("TESTUSDT", expanded, state), [])

    def test_close_below_ema12_confirms_without_crossover_requirement(self):
        state = {
            "observing": True,
            "touched_lines": ["中锋EMA144"],
            "touch_timestamp_ms": 699 * 3_600_000,
            "last_processed_timestamp_ms": 699 * 3_600_000,
        }
        candles = [candle(i * 3_600_000) for i in range(700)]
        candles.append(candle(700 * 3_600_000, close=99.0, high=100.0, low=99.0))
        signals = detect_formal_signals("TESTUSDT", candles, state)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["filter_side"], "下方")
        self.assertFalse(state["observing"])

    def test_close_equal_to_ema12_keeps_observation_active(self):
        state = {
            "observing": True,
            "touched_lines": ["中锋EMA144"],
            "touch_timestamp_ms": 698 * 3_600_000,
            "last_processed_timestamp_ms": 698 * 3_600_000,
        }
        candles = [candle(i * 3_600_000) for i in range(699)]
        candles.append(candle(699 * 3_600_000, close=100.0))
        signals = detect_formal_signals("TESTUSDT", candles, state)
        self.assertEqual(signals, [])
        self.assertTrue(state["observing"])
        self.assertEqual(state["last_processed_timestamp_ms"], 699 * 3_600_000)


if __name__ == "__main__":
    unittest.main()
