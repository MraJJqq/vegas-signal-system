import pandas as pd

from vegas_signal_system.rules import scan_symbol


def make_frame(n=180, direction="up"):
    if direction == "up":
        close = [100.0 + i * 0.5 for i in range(n)]
    else:
        close = [200.0 - i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
        "open": close,
        "high": [value + 1 for value in close],
        "low": [value - 1 for value in close],
        "close": close,
        "volume": [100.0] * n,
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
        "timeframes": {
            "direction_sources": ["4h", "8h"],
            "entry_watch": ["1h", "2h"],
        },
        "indicators": {
            "filter_sma": 2,
            "entry_ema": 36,
            "direction_ema": 144,
            "direction_ema_alternative": 169,
            "major_ema": 576,
        },
    }


def symbol():
    return {"id": "BTC", "name": "比特币", "enabled": True}


def test_direction_conflict_blocks_trade():
    provider = MemoryProvider({
        "4h": make_frame(direction="up"),
        "8h": make_frame(direction="down"),
        "1h": make_frame(),
        "2h": make_frame(),
    })
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "NO_TRADE_CONFLICT"
    assert "空仓" in result.message


def test_aligned_direction_is_observation_not_entry_signal():
    provider = MemoryProvider({
        "4h": make_frame(direction="up"),
        "8h": make_frame(direction="up"),
        "1h": make_frame(),
        "2h": make_frame(),
    })
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "WATCH_ENTRY_CONDITIONS"
    assert result.entry_timeframe in {"1h", "2h"}
    assert "不视为正式信号" in result.message


def test_missing_direction_data_never_emits_entry():
    provider = MemoryProvider({"4h": make_frame(), "1h": make_frame()})
    result = scan_symbol(symbol(), provider, config())
    assert result.status == "DATA_UNAVAILABLE"
    assert result.entry_timeframe is None
