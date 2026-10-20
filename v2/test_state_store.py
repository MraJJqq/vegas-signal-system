import json
import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_observations_are_scoped_by_symbol_and_timeframe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.set_observation("BTCUSDT", "1h", True)
            self.assertTrue(store.observation_active("BTCUSDT", "1h"))
            self.assertFalse(store.observation_active("BTCUSDT", "2h"))
            self.assertFalse(store.observation_active("HYPEUSDT", "1h"))
            reloaded = StateStore(path)
            self.assertTrue(reloaded.observation_active("BTCUSDT", "1h"))

    def test_signal_dedup_is_symbol_timeframe_direction_and_candle_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            args = ("BTCUSDT", "1h", "long", "2026-10-20T10:00:00Z")
            self.assertFalse(store.signal_seen(*args))
            store.mark_signal_seen(*args)
            self.assertTrue(StateStore(store.path).signal_seen(*args))
            self.assertFalse(store.signal_seen("BTCUSDT", "2h", "long", args[-1]))
            self.assertFalse(store.signal_seen("BTCUSDT", "1h", "short", args[-1]))
            self.assertFalse(store.signal_seen("BTCUSDT", "1h", "long", "2026-10-20T11:00:00Z"))

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                StateStore(path)


if __name__ == "__main__":
    unittest.main()
