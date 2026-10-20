import unittest
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


class TimeframeContractTests(unittest.TestCase):
    @unittest.skipIf(yaml is None, "PyYAML is unavailable")
    def test_touch_and_signal_timeframes_are_1h_2h_4h(self):
        config = yaml.safe_load(Path(__file__).with_name("settings.yaml").read_text())
        self.assertEqual(config["timeframes"]["touch_and_signal"], ["1h", "2h", "4h"])

    @unittest.skipIf(yaml is None, "PyYAML is unavailable")
    def test_each_timeframe_uses_its_own_ema12_and_only_closed_candles(self):
        config = yaml.safe_load(Path(__file__).with_name("settings.yaml").read_text())
        self.assertEqual(config["indicators"]["formal_signal_filter_ema"], 12)
        self.assertTrue(config["rules"]["require_completed_candle"])
        self.assertEqual(config["rules"]["equality_is_signal"], False)

    @unittest.skipIf(yaml is None, "PyYAML is unavailable")
    def test_observation_state_and_dedup_are_timeframe_scoped(self):
        config = yaml.safe_load(Path(__file__).with_name("settings.yaml").read_text())
        self.assertIn("timeframe", config["rules"]["observation_state_key"])
        self.assertIn("timeframe", config["rules"]["deduplication_key"])

    @unittest.skipIf(yaml is None, "PyYAML is unavailable")
    def test_notifications_are_formal_signals_only_and_no_orders(self):
        config = yaml.safe_load(Path(__file__).with_name("settings.yaml").read_text())
        self.assertTrue(config["notifications"]["send_formal_signals_only"])
        self.assertFalse(config["execution"]["place_orders"])


if __name__ == "__main__":
    unittest.main()
