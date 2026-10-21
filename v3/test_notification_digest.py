"""Tests for V3 ntfy digest and stable signal deduplication."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from notification_digest import (
    ConfirmedSignal, format_digest, load_daily_state,
    save_daily_state, update_daily_digest,
)


DAY = date(2026, 10, 21)


def signal(candle_time="2026-10-21T04:00:00+00:00", symbol="BTCUSDT"):
    return ConfirmedSignal.from_closed_candle(
        symbol=symbol, direction="LONG", timeframe="4H",
        candle_time=candle_time, close=123.4,
    )


class NotificationDigestTests(unittest.TestCase):
    def test_stable_id_deduplicates_same_closed_candle(self):
        state = {"local_day": DAY.isoformat(), "signals": []}
        state, new = update_daily_digest(state, [signal(), signal()], DAY)
        self.assertEqual(len(new), 1)
        self.assertEqual(len(state["signals"]), 1)
        state, new_again = update_daily_digest(state, [signal()], DAY)
        self.assertEqual(new_again, [])
        self.assertEqual(len(state["signals"]), 1)

    def test_different_closed_candle_is_a_new_signal_event(self):
        state = {"local_day": DAY.isoformat(), "signals": []}
        state, first = update_daily_digest(state, [signal()], DAY)
        state, second = update_daily_digest(
            state, [signal(candle_time="2026-10-21T08:00:00+00:00")], DAY
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(len(state["signals"]), 2)

    def test_date_rollover_discards_previous_day_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_daily_state(path, {
                "local_day": "2026-10-20",
                "signals": [{"signal_id": "yesterday"}],
            })
            state = load_daily_state(path, DAY)
            self.assertEqual(state, {"local_day": DAY.isoformat(), "signals": []})

    def test_state_round_trip_and_same_day_reminder(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state, new = update_daily_digest(
                {"local_day": DAY.isoformat(), "signals": []}, [signal()], DAY
            )
            save_daily_state(path, state)
            loaded = load_daily_state(path, DAY)
            self.assertEqual(loaded["signals"][0]["signal_id"], signal().signal_id)
            message = format_digest(loaded, [])
            self.assertIn("本次没有新信号", message)
            self.assertIn("BTCUSDT", message)
            self.assertIn("▲  LONG  ·  做多", message)
            self.assertIn("4H 正式信号", message)

    def test_rejects_non_4h_signal(self):
        with self.assertRaises(ValueError):
            ConfirmedSignal.from_closed_candle(
                symbol="BTCUSDT", direction="LONG", timeframe="8H",
                candle_time="2026-10-21T04:00:00+00:00", close=100,
            )

    def test_invalid_direction_rejected(self):
        with self.assertRaises(ValueError):
            ConfirmedSignal.from_closed_candle(
                symbol="BTCUSDT", direction="BUY", timeframe="4H",
                candle_time="2026-10-21T04:00:00+00:00", close=100,
            )


if __name__ == "__main__":
    unittest.main()
