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
        self.assertEqual(signals[0]["candle_timestamp_ms"], expanded[-1]["timestamp_ms"])
        self.assertFalse(state["observing"])
        self.assertEqual(detect_formal_signals("TESTUSDT", expanded, state), [])

    def test_touch_candle_is_not_also_formal_signal(self):
        state = {}
        candles = [candle(i * 3_600_000) for i in range(700)]
        signals = detect_formal_signals("TESTUSDT", candles, state)
        self.assertEqual(signals, [])
        self.assertTrue(state["observing"])


if __name__ == "__main__":
    unittest.main()
