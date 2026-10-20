import pandas as pd

from vegas_signal_system.indicators import add_indicators
from vegas_signal_system.rules import _last_candle_touches_ema


def indicator_frame():
    close = [100.0 + i * 0.25 for i in range(20)]
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(close), freq="h", tz="UTC"),
        "open": close,
        "high": [value + 1.0 for value in close],
        "low": [value - 1.0 for value in close],
        "close": close,
        "volume": [10.0] * len(close),
    })
    return add_indicators(frame, {
        "indicators": {
            "filter_sma": 2,
            "entry_ema": 3,
            "direction_ema": 5,
            "direction_ema_alternative": 6,
            "major_ema": 10,
        }
    })


def test_touch_is_inclusive_when_candle_high_equals_ema():
    frame = indicator_frame()
    ema = float(frame.iloc[-1]["ema_5"])
    frame.loc[frame.index[-1], "high"] = ema
    frame.loc[frame.index[-1], "low"] = ema - 0.5
    assert _last_candle_touches_ema(frame, 5)


def test_touch_is_inclusive_when_candle_low_equals_ema():
    frame = indicator_frame()
    ema = float(frame.iloc[-1]["ema_5"])
    frame.loc[frame.index[-1], "low"] = ema
    frame.loc[frame.index[-1], "high"] = ema + 0.5
    assert _last_candle_touches_ema(frame, 5)


def test_no_touch_when_entire_candle_is_above_ema():
    frame = indicator_frame()
    ema = float(frame.iloc[-1]["ema_5"])
    frame.loc[frame.index[-1], "low"] = ema + 0.01
    frame.loc[frame.index[-1], "high"] = ema + 1.0
    assert not _last_candle_touches_ema(frame, 5)


def test_no_touch_when_ema_is_unavailable():
    frame = indicator_frame()
    frame.loc[frame.index[-1], "ema_5"] = float("nan")
    assert not _last_candle_touches_ema(frame, 5)
