import unittest

from rules import candle_touches_ema144, evaluate_entry


def candle(*, low=98, high=102, close=101, ema144=100, ema12=100,
           timestamp="2026-10-20T10:00:00Z", complete=True):
    return {
        "low": low, "high": high, "close": close,
        "ema144": ema144, "ema12": ema12,
        "timestamp": timestamp, "complete": complete,
    }


class TouchTests(unittest.TestCase):
    def test_overlap_counts_as_touch(self):
        self.assertTrue(candle_touches_ema144(candle()))

    def test_outside_range_is_not_touch(self):
        self.assertFalse(candle_touches_ema144(candle(low=101, high=103)))

    def test_missing_ema_is_not_touch(self):
        self.assertFalse(candle_touches_ema144({"low": 1, "high": 2}))


class EntryRuleTests(unittest.TestCase):
    def test_touch_alone_does_not_signal(self):
        row = candle(close=99, ema12=100)
        result = evaluate_entry([row], "up")
        self.assertEqual(result.status, "WAIT_FILTER_CLOSE")
        self.assertTrue(result.observation_active)

    def test_long_only_after_close_above_filter(self):
        result = evaluate_entry([candle(close=101, ema12=100)], "up")
        self.assertEqual(result.status, "ENTRY_SIGNAL_LONG")

    def test_short_only_after_close_below_filter(self):
        result = evaluate_entry([candle(close=99, ema12=100)], "down")
        self.assertEqual(result.status, "ENTRY_SIGNAL_SHORT")

    def test_equal_filter_is_not_signal(self):
        result = evaluate_entry([candle(close=100, ema12=100)], "up")
        self.assertEqual(result.status, "WAIT_FILTER_CLOSE")

    def test_direction_gate_blocks(self):
        result = evaluate_entry([candle()], "conflict")
        self.assertEqual(result.status, "BLOCKED_DIRECTION")

    def test_prior_observation_persists_without_new_touch(self):
        result = evaluate_entry(
            [candle(low=102, high=104, close=101, ema144=100, ema12=100)],
            "up",
            observation_active=True,
        )
        self.assertEqual(result.status, "ENTRY_SIGNAL_LONG")
        self.assertTrue(result.observation_active)

    def test_incomplete_latest_candle_never_signals(self):
        result = evaluate_entry([candle(close=101, ema12=100, complete=False)], "up")
        self.assertEqual(result.status, "INCOMPLETE_CANDLE")


if __name__ == "__main__":
    unittest.main()
