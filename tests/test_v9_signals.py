import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
from vegas_signals import detect_formal_signals

HOUR = 3600000
def candle(ts, close=100.0, high=100.0, low=100.0):
    return {"timestamp_ms": ts, "open": close, "high": high, "low": low, "close": close, "closed": True}

class V9SignalTests(unittest.TestCase):
    def test_4h_touch_then_1h_signal_once(self):
        # Flat data creates valid EMAs; 4H candle range touches EMA144.
        state = {}
        c4 = [candle(i * 4 * HOUR) for i in range(700)]
        c4[-1] = candle(699 * 4 * HOUR, high=101, low=99)
        c1 = [candle(i * HOUR) for i in range(2800)]
        self.assertEqual(detect_formal_signals("TESTUSDT", c1, c4, state), [])
        self.assertTrue(state["observing"])
        # A later 1H close above its EMA12 confirms once.
        c1.append(candle(2800 * HOUR, close=101, high=101, low=101))
        signals = detect_formal_signals("TESTUSDT", c1, c4, state)
        self.assertEqual(len(signals), 1)
        self.assertTrue(signals[0]["formal_signal"])
        self.assertEqual(signals[0]["filter_line"], "1H EMA12")
        self.assertEqual(detect_formal_signals("TESTUSDT", c1, c4, state), [])

    def test_touch_observation_persists_after_price_leaves_area(self):
        state = {"observing": True, "touched_lines": ["中锋EMA144"],
                 "touch_timestamp_ms": 100 * 4 * HOUR,
                 "last_processed_1h_timestamp_ms": 403 * HOUR,
                 "last_processed_4h_timestamp_ms": 100 * 4 * HOUR}
        c4 = [candle(i * 4 * HOUR) for i in range(101)]
        c1 = [candle(i * HOUR) for i in range(404)]
        c1.append(candle(404 * HOUR, close=101, high=101, low=101))
        signals = detect_formal_signals("TESTUSDT", c1, c4, state)
        self.assertEqual(len(signals), 1)
        self.assertFalse(state["observing"])

    def test_equal_ema12_does_not_confirm(self):
        state = {"observing": True, "touched_lines": ["中锋EMA144"],
                 "touch_timestamp_ms": 100 * 4 * HOUR,
                 "last_processed_1h_timestamp_ms": 403 * HOUR,
                 "last_processed_4h_timestamp_ms": 100 * 4 * HOUR}
        c4 = [candle(i * 4 * HOUR) for i in range(101)]
        c1 = [candle(i * HOUR) for i in range(404)]
        c1.append(candle(404 * HOUR))
        self.assertEqual(detect_formal_signals("TESTUSDT", c1, c4, state), [])
        self.assertTrue(state["observing"])

if __name__ == "__main__":
    unittest.main()
