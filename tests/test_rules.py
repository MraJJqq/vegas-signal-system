import pandas as pd
from vegas_signal_system.indicators import add_indicators
from vegas_signal_system.rules import scan_symbol


def make_frame(n=180, direction="up"):
    close = [100.0 + i * 0.5 for i in range(n)] if direction == "up" else [200.0 - i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
        "open": close, "high": [v + 1 for v in close], "low": [v - 1 for v in close],
        "close": close, "volume": [100.0] * n,
    })


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
                  "entry_midline_touch_mode": "high_low_overlap"},
    }


def symbol():
    return {"id": "BTC", "name": "比特币", "enabled": True}


def set_last_candle_to_ema(frame):
    with_indicators = add_indicators(frame, config())
    ema = float(with_indicators.iloc[-1]["ema_144"])
    frame.loc[frame.index[-1], "low"] = min(float(frame.iloc[-1]["low"]), ema)
    frame.loc[frame.index[-1], "high"] = max(float(frame.iloc[-1]["high"]), ema)
    return frame


def test_direction_conflict_blocks_trade():
    cfg = config()
    cfg["timeframes"]["direction_sources"] = ["4h", "8h"]
    provider = MemoryProvider({"4h": make_frame(direction="up"),
                               "8h": make_frame(direction="down"), "1h": make_frame(), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, cfg)
    assert result.status == "NO_TRADE_CONFLICT"
    assert "空仓" in result.message


def test_aligned_direction_without_touch_remains_observation():
    provider = MemoryProvider({"4h": make_frame(), "1h": make_frame(), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONDITIONS"
    assert result.entry_timeframe in {"1h", "2h"}
    assert "未触碰EMA144" in result.message
    assert "不视为正式进场信号" in result.message


def test_latest_candle_wick_overlap_records_touch_but_not_entry():
    provider = MemoryProvider({"4h": make_frame(),
                               "1h": set_last_candle_to_ema(make_frame()), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONFIRMATION"
    assert result.entry_timeframe == "1h"
    assert "覆盖EMA144" in result.message
    assert "不视为正式进场信号" in result.message


def test_touch_in_2h_is_detected_when_1h_does_not_touch():
    provider = MemoryProvider({"4h": make_frame(),
                               "1h": make_frame(), "2h": set_last_candle_to_ema(make_frame())})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONFIRMATION"
    assert result.entry_timeframe == "2h"


def test_4h_only_direction_does_not_require_8h_data():
    provider = MemoryProvider({"4h": make_frame(), "1h": make_frame(), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONDITIONS"
    assert result.direction_4h == "up"
    assert result.direction_8h == "unavailable"


def test_missing_required_4h_direction_data_never_emits_entry():
    provider = MemoryProvider({"1h": make_frame(), "2h": make_frame()})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "DATA_UNAVAILABLE"
    assert result.entry_timeframe is None
