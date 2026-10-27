import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
from vegas_signals import detect_formal_signals

HOUR = 3600000
def candle(ts, close=100.0, high=100.0, low=100.0):
    return {"timestamp_ms": ts, "open": close, "high": high, "low": low, "close": close, "closed": True}

class V9SignalTests(unittest.TestCase):
    def test_4h_touch_then_2h_signal_once(self):
        # Flat data creates valid EMAs; 4H candle range touches EMA144.
        state = {}
        c4 = [candle(i * 4 * HOUR) for i in range(700)]
        c4[-1] = candle(699 * 4 * HOUR, high=101, low=99)
        c2 = [candle(i * 2 * HOUR) for i in range(1400)]
        self.assertEqual(detect_formal_signals("TESTUSDT", c2, c4, state), [])
        self.assertTrue(state["observing"])
        # A later 2H close above its EMA12 confirms once.
        c2.append(candle(1400 * 2 * HOUR, close=101, high=101, low=101))
        signals = detect_formal_signals("TESTUSDT", c2, c4, state)
        self.assertEqual(len(signals), 1)
        self.assertTrue(signals[0]["formal_signal"])
        self.assertEqual(signals[0]["timeframe"], "2H")
        self.assertEqual(signals[0]["filter_line"], "2H EMA12")
        self.assertEqual(detect_formal_signals("TESTUSDT", c2, c4, state), [])

    def test_touch_observation_persists_after_price_leaves_area(self):
        state = {"observing": True, "touched_lines": ["中锋EMA144"],
                 "touch_timestamp_ms": 100 * 4 * HOUR,
                 "last_processed_2h_timestamp_ms": 201 * 2 * HOUR,
                 "last_processed_4h_timestamp_ms": 100 * 4 * HOUR}
        c4 = [candle(i * 4 * HOUR) for i in range(101)]
        c2 = [candle(i * 2 * HOUR) for i in range(202)]
        c2.append(candle(202 * 2 * HOUR, close=101, high=101, low=101))
        signals = detect_formal_signals("TESTUSDT", c2, c4, state)
        self.assertEqual(len(signals), 1)
        self.assertFalse(state["observing"])

    def test_equal_ema12_does_not_confirm(self):
        state = {"observing": True, "touched_lines": ["中锋EMA144"],
                 "touch_timestamp_ms": 100 * 4 * HOUR,
                 "last_processed_2h_timestamp_ms": 201 * 2 * HOUR,
                 "last_processed_4h_timestamp_ms": 100 * 4 * HOUR}
        c4 = [candle(i * 4 * HOUR) for i in range(101)]
        c2 = [candle(i * 2 * HOUR) for i in range(202)]
        c2.append(candle(202 * 2 * HOUR))
        self.assertEqual(detect_formal_signals("TESTUSDT", c2, c4, state), [])
        self.assertTrue(state["observing"])

if __name__ == "__main__":
    unittest.main()
