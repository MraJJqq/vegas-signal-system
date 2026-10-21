import unittest

from signal_system_v5 import Candle, V5WatchStates, evaluate_candle


class V5Tests(unittest.TestCase):
    def test_touch_does_not_signal_same_candle(self):
        states = V5WatchStates.fresh()
        events = evaluate_candle("4H", Candle(105, 107, 104), 100, 104, 106, 580, 590, states)
        self.assertEqual(events, [])
        self.assertTrue(states.midline.active)

    def test_midline_and_red_peak_watches_are_independent(self):
        states = V5WatchStates.fresh()
        states.midline.active = True
        # Red peak touch starts its own watch, without cancelling midline.
        events = evaluate_candle("4H", Candle(110, 581, 109), 100, 104, 106, 580, 590, states)
        self.assertEqual(events, [])
        self.assertTrue(states.midline.active)
        self.assertTrue(states.red_peak.active)

    def test_confirmation_emits_for_each_active_watch(self):
        states = V5WatchStates.fresh()
        states.midline.active = True
        states.red_peak.active = True
        events = evaluate_candle("4H", Candle(112, 113, 111), 110, 104, 106, 580, 590, states)
        self.assertEqual([e.observation for e in events], ["midline", "red_peak"])
        self.assertEqual([e.direction for e in events], ["LONG", "LONG"])
        self.assertFalse(states.midline.active)
        self.assertFalse(states.red_peak.active)

    def test_unclosed_candle_does_not_change_state(self):
        states = V5WatchStates.fresh()
        events = evaluate_candle("4H", Candle(112, 113, 111, closed=False), 110, 104, 106, 580, 590, states)
        self.assertEqual(events, [])
        self.assertFalse(states.midline.active)
        self.assertFalse(states.red_peak.active)

    def test_watch_has_no_timeout(self):
        states = V5WatchStates.fresh()
        states.midline.active = True
        for _ in range(100):
            events = evaluate_candle("4H", Candle(105, 105.5, 104.5), 106, 104, 106, 580, 590, states)
            self.assertEqual(events, [])
        self.assertTrue(states.midline.active)


if __name__ == "__main__":
    unittest.main()
