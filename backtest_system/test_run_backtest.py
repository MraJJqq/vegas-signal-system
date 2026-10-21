from datetime import timezone
import json
import tempfile
import unittest
from pathlib import Path

from run_backtest import load_signals, parse_datetime
from v1_trading_system import Direction


class V1RunnerTests(unittest.TestCase):
    def test_parse_datetime_normalizes_to_utc(self):
        value = parse_datetime("2026-01-01T08:00:00+08:00")
        self.assertEqual(value.tzinfo, timezone.utc)
        self.assertEqual(value.isoformat(), "2026-01-01T00:00:00+00:00")

    def test_load_confirmed_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signals.json"
            path.write_text(json.dumps([{
                "symbol": "XAUUSDT",
                "timeframe": "4H",
                "timestamp": "2026-01-01T04:00:00Z",
                "direction": "LONG",
                "signal_close": 100.0
            }]), encoding="utf-8")
            signals = load_signals(path)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].symbol, "XAUUSDT")
        self.assertEqual(signals[0].direction, Direction.LONG)

    def test_reject_invalid_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signals.json"
            path.write_text(json.dumps([{
                "symbol": "XAUUSDT",
                "timeframe": "4H",
                "timestamp": "2026-01-01T04:00:00Z",
                "direction": "SIDEWAYS",
                "signal_close": 100.0
            }]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_signals(path)

    def test_reject_naive_datetime(self):
        with self.assertRaises(ValueError):
            parse_datetime("2026-01-01T04:00:00")


if __name__ == "__main__":
    unittest.main()
