import unittest

from signal_system_v4 import Candle, WatchState, evaluate_candle, scan_closed_candles


class V4RuleTests(unittest.TestCase):
    def test_unclosed_candle_never_emits(self):
        state = WatchState(active=True)
        event = evaluate_candle("4H", Candle(110, 111, 109, closed=False), 100, 104, 105, state)
        self.assertIsNone(event)
        self.assertTrue(state.active)

    def test_only_4h_supported(self):
        with self.assertRaises(ValueError):
            evaluate_candle("1H", Candle(110, 111, 109), 100, 104, 105, WatchState())

    def test_touch_starts_observation_but_does_not_signal_same_candle(self):
        state = WatchState()
        event = evaluate_candle("4H", Candle(105, 106, 104), 100, 104, 106, state)
        self.assertIsNone(event)
        self.assertTrue(state.active)

    def test_long_requires_close_above_midline_and_filter(self):
        rows = [
            (Candle(105, 107, 104), 100, 104, 106, 580, 590),
            (Candle(112, 113, 111), 110, 104, 106, 580, 590),
        ]
        events = scan_closed_candles("4H", rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].direction, "LONG")

    def test_observation_has_no_timeout(self):
        state = WatchState(active=True)
        for _ in range(100):
            event = evaluate_candle("4H", Candle(105, 105.5, 104.5), 106, 104, 106, state)
            self.assertIsNone(event)
        self.assertTrue(state.active)


if __name__ == "__main__":
    unittest.main()
