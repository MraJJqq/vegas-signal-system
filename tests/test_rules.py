import pandas as pd
from vegas_signal_system.indicators import add_indicators
from vegas_signal_system.rules import scan_symbol


def make_frame(n=220, direction="up", touch_history=True):
    close = [100.0 + i * 0.5 for i in range(n)] if direction == "up" else [200.0 - i * 0.5 for i in range(n)]
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
        "open": close, "high": [v + 1 for v in close], "low": [v - 1 for v in close],
        "close": close, "volume": [100.0] * n,
    })
    if touch_history:
        with_indicators = add_indicators(frame, config())
        idx = 170
        ema = float(with_indicators.loc[idx, "ema_144"])
        frame.loc[idx, "low"] = min(float(frame.loc[idx, "low"]), ema) - 0.1
        frame.loc[idx, "high"] = max(float(frame.loc[idx, "high"]), ema) + 0.1
    return frame


class MemoryProvider:
    def __init__(self, frames):
        self.frames = frames

    def load(self, symbol_id, timeframe):
        if timeframe not in self.frames:
            raise FileNotFoundError(f"missing {timeframe}")
        return self.frames[timeframe].copy()


def config():
    return {
        "timeframes": {"direction_sources": ["4h"], "entry_watch": ["1h", "2h"]},
        "indicators": {"filter_sma": 2, "entry_ema": 36, "direction_ema": 144,
                       "direction_ema_alternative": 169, "major_ema": 576},
        "rules": {"require_entry_midline_touch": True, "entry_midline_ema": 144,
                  "entry_filter_ema": 12, "entry_midline_touch_mode": "high_low_overlap"},
    }


def symbol():
    return {"id": "BTC", "name": "比特币", "enabled": True}


def test_direction_conflict_blocks_trade():
    cfg = config()
    cfg["timeframes"]["direction_sources"] = ["4h", "8h"]
    provider = MemoryProvider({"4h": make_frame(direction="up"),
                               "8h": make_frame(direction="down"), "1h": make_frame(), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, cfg)
    assert result.status == "NO_TRADE_CONFLICT"
    assert "空仓" in result.message


def test_historical_touch_keeps_observation_active_and_emits_long_signal():
    provider = MemoryProvider({"4h": make_frame(direction="up"),
                               "1h": make_frame(direction="up", touch_history=True),
                               "2h": make_frame(direction="up", touch_history=False)})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "ENTRY_SIGNAL_LONG"
    assert result.entry_timeframe == "1h"
    assert "持续有效" in result.message
    assert "EMA12上方" in result.message


def test_historical_touch_and_close_below_filter_emits_short_when_direction_down():
    provider = MemoryProvider({"4h": make_frame(direction="down"),
                               "1h": make_frame(direction="down", touch_history=True),
                               "2h": make_frame(direction="down", touch_history=False)})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "ENTRY_SIGNAL_SHORT"
    assert result.entry_timeframe == "1h"
    assert "EMA12下方" in result.message


def test_no_historical_touch_means_no_entry_signal():
    provider = MemoryProvider({"4h": make_frame(direction="up"),
                               "1h": make_frame(direction="up", touch_history=False),
                               "2h": make_frame(direction="up", touch_history=False)})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONDITIONS"


def test_missing_required_direction_data_never_emits_entry():
    provider = MemoryProvider({"1h": make_frame(direction="up"), "2h": make_frame(direction="up")})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "DATA_UNAVAILABLE"
    assert result.entry_timeframe is None
