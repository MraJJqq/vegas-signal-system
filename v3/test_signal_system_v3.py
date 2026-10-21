"""Unit tests for the independent Vegas Signal System V3 module."""
import unittest

from signal_system_v3 import Candle, WatchState, evaluate_candle


class SignalSystemV3Tests(unittest.TestCase):
    def test_only_4h_and_8h_are_allowed(self):
        with self.assertRaises(ValueError):
            evaluate_candle("1H", Candle(110, 111, 109), 105, 100, 102, WatchState())

    def test_unclosed_candle_never_emits_signal(self):
        state = WatchState()
        event = evaluate_candle("4H", Candle(110, 111, 109, closed=False),
                                105, 100, 102, state)
        self.assertIsNone(event)
        self.assertFalse(state.active)

    def test_touch_starts_observation_but_does_not_immediately_signal(self):
        state = WatchState()
        event = evaluate_candle("4H", Candle(101, 103, 99), 105, 100, 102, state)
        self.assertIsNone(event)
        self.assertTrue(state.active)

    def test_long_signal_requires_close_above_midline_and_ema12(self):
        state = WatchState()
        evaluate_candle("4H", Candle(101, 103, 99), 105, 100, 102, state)
        event = evaluate_candle("4H", Candle(108, 109, 107), 105, 100, 102, state)
        self.assertIsNotNone(event)
        self.assertEqual(event.direction, "LONG")
        self.assertEqual(event.timeframe, "4H")
        self.assertFalse(state.active)

    def test_short_signal_requires_close_below_midline_and_ema12(self):
        state = WatchState()
        evaluate_candle("8H", Candle(101, 103, 99), 105, 100, 102, state)
        event = evaluate_candle("8H", Candle(94, 95, 93), 97, 100, 102, state)
        self.assertIsNotNone(event)
        self.assertEqual(event.direction, "SHORT")
        self.assertEqual(event.timeframe, "8H")

    def test_observation_has_no_time_limit(self):
        state = WatchState()
        evaluate_candle("4H", Candle(101, 103, 99), 105, 100, 102, state)
        for _ in range(100):
            event = evaluate_candle("4H", Candle(104, 106, 103), 105, 100, 102, state)
            self.assertIsNone(event)
        self.assertTrue(state.active)

    def test_touch_alone_is_not_a_signal(self):
        state = WatchState()
        event = evaluate_candle("8H", Candle(101, 103, 99), 100, 100, 102, state)
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
