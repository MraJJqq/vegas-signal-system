import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from signal_system_v6 import Candle, V6WatchStates, evaluate_candle
from notification_digest_v6 import ConfirmedSignal, update_daily_digest
from datetime import date

class V6Tests(unittest.TestCase):
    def test_unclosed_candle_never_signals(self):
        states = V6WatchStates.fresh()
        events = evaluate_candle("4H", Candle(120, 121, 119, False), 110, 100, 105, 70, 65, states)
        self.assertEqual(events, [])
        self.assertFalse(states.midline.active)

    def test_touch_candle_only_starts_observation(self):
        states = V6WatchStates.fresh()
        events = evaluate_candle("4H", Candle(120, 125, 60, True), 110, 100, 105, 70, 65, states)
        self.assertEqual(events, [])
        self.assertTrue(states.midline.active)
        self.assertTrue(states.red_peak.active)

    def test_rejects_unsupported_timeframe(self):
        with self.assertRaises(ValueError): evaluate_candle("1H", Candle(120,121,119), 110,100,105,70,65,V6WatchStates.fresh())

    def test_signal_id_deduplication(self):
        signal = ConfirmedSignal.from_closed_candle(symbol="BTCUSDT", direction="LONG", timeframe="4H", candle_time="2026-10-21T08:00:00+00:00", close=100)
        state, fresh = update_daily_digest({"local_day":"2026-10-21","signals":[]}, [signal, signal], date(2026,10,21))
        self.assertEqual(len(fresh), 1)
        self.assertEqual(len(state["signals"]), 1)

if __name__ == "__main__": unittest.main()