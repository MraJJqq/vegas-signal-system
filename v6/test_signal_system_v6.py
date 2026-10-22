import unittest
from signal_system_v6 import Candle, WatchStates, evaluate_candle

class V6Tests(unittest.TestCase):
    def test_touch_only_starts_watch_without_signal(self):
        states = WatchStates()
        events = evaluate_candle(Candle(105, 107, 104), 100, 104, 106, 580, 590, states)
        self.assertEqual(events, [])
        self.assertTrue(states.midline)

    def test_filter_side_confirms_existing_watch(self):
        states = WatchStates(midline=True)
        events = evaluate_candle(Candle(112, 113, 111), 110, 104, 106, 580, 590, states)
        self.assertEqual([(e.observation, e.direction) for e in events], [("midline", "LONG")])
        self.assertFalse(states.midline)

    def test_midline_and_red_peak_are_independent(self):
        states = WatchStates(midline=True)
        events = evaluate_candle(Candle(585, 591, 580), 590, 104, 106, 580, 590, states)
        self.assertEqual([(e.observation, e.direction) for e in events], [("midline", "SHORT")])
        self.assertFalse(states.midline)
        self.assertTrue(states.red_peak)

    def test_unclosed_candle_cannot_change_state(self):
        states = WatchStates()
        self.assertEqual(evaluate_candle(Candle(112, 113, 111, False), 110, 104, 106, 580, 590, states), [])
        self.assertFalse(states.midline)
        self.assertFalse(states.red_peak)

if __name__ == "__main__":
    unittest.main()
