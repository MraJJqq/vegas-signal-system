import unittest

from bitget_market_data_v5 import BitgetAPIError, discover_v5_symbols

from signal_system_v5 import Candle, V5WatchStates, evaluate_candle


class V5Tests(unittest.TestCase):
    def test_discovery_includes_crypto_and_rwa_but_excludes_gold_oil(self):
        def fake_request(url):
            return {"code": "00000", "data": [
                {"symbol": "BTCUSDT", "quoteCoin": "USDT", "symbolStatus": "normal", "isRwa": "NO"},
                {"symbol": "HYPEUSDT", "quoteCoin": "USDT", "symbolStatus": "normal", "isRwa": "NO"},
                {"symbol": "AAPLUSDT", "quoteCoin": "USDT", "symbolStatus": "normal", "isRwa": "YES"},
                {"symbol": "XAUUSDT", "quoteCoin": "USDT", "symbolStatus": "normal", "isRwa": "YES"},
                {"symbol": "CLUSDT", "quoteCoin": "USDT", "symbolStatus": "normal", "isRwa": "YES"},
                {"symbol": "OFFUSDT", "quoteCoin": "USDT", "symbolStatus": "offline", "isRwa": "NO"},
            ]}
        self.assertEqual(discover_v5_symbols(fake_request), ["AAPLUSDT", "BTCUSDT", "CLUSDT", "HYPEUSDT", "XAUUSDT"])

    def test_discovery_fails_on_invalid_contract_list(self):
        with self.assertRaises(BitgetAPIError):
            discover_v5_symbols(lambda url: {"code": "00000", "data": None})


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
