import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v9"))
from vegas_signals import detect_formal_signals

def candle(ts, close=100.0, high=100.0, low=100.0):
    return {"timestamp_ms":ts,"open":close,"high":high,"low":low,"close":close,"closed":True}

class V9SignalTests(unittest.TestCase):
    def test_observation_then_confirmation_once(self):
        state={}; initial=[candle(i*3600000) for i in range(700)]
        self.assertEqual(detect_formal_signals("TESTUSDT",initial,state),[])
        self.assertTrue(state["observing"])
        expanded=initial+[candle(700*3600000,close=101,high=101,low=100)]
        signals=detect_formal_signals("TESTUSDT",expanded,state)
        self.assertEqual(len(signals),1); self.assertTrue(signals[0]["formal_signal"])
        self.assertEqual(signals[0]["filter_side"],"上方")
        self.assertEqual(detect_formal_signals("TESTUSDT",expanded,state),[])
    def test_close_below_ema12_confirms(self):
        state={"observing":True,"touched_lines":["中锋EMA144"],"touch_timestamp_ms":699*3600000,"last_processed_timestamp_ms":699*3600000}
        candles=[candle(i*3600000) for i in range(700)]+[candle(700*3600000,close=99,high=100,low=99)]
        signals=detect_formal_signals("TESTUSDT",candles,state)
        self.assertEqual(len(signals),1); self.assertEqual(signals[0]["filter_side"],"下方")
    def test_equal_to_ema12_keeps_observation(self):
        state={"observing":True,"touched_lines":["中锋EMA144"],"touch_timestamp_ms":698*3600000,"last_processed_timestamp_ms":698*3600000}
        candles=[candle(i*3600000) for i in range(699)]+[candle(699*3600000)]
        self.assertEqual(detect_formal_signals("TESTUSDT",candles,state),[])
        self.assertTrue(state["observing"])
    def test_touch_candle_cannot_confirm_itself(self):
        state={"observing":True,"touched_lines":["中锋EMA144"],"touch_timestamp_ms":700*3600000,"last_processed_timestamp_ms":699*3600000}
        candles=[candle(i*3600000) for i in range(700)]+[candle(700*3600000,close=101,high=101,low=100)]
        self.assertEqual(detect_formal_signals("TESTUSDT",candles,state),[])
        self.assertTrue(state["observing"])
        candles.append(candle(701*3600000,close=101,high=101,low=100))
        signals=detect_formal_signals("TESTUSDT",candles,state)
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0]["candle_timestamp_ms"],701*3600000)
if __name__=="__main__": unittest.main()
