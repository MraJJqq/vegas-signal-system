import pandas as pd
import pytest

from vegas_signal_system.data import resample_ohlcv


def hourly_frame(count=20):
    timestamps = pd.date_range("2026-01-01T00:00:00Z", periods=count, freq="h")
    values = [100.0 + i for i in range(count)]
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": values,
        "high": [v + 2 for v in values],
        "low": [v - 2 for v in values],
        "close": [v + 1 for v in values],
        "volume": [10.0] * count,
    })


def test_resample_aggregates_ohlcv_and_excludes_unclosed_candle():
    frame = hourly_frame(12)
    result = resample_ohlcv(frame, "4h", now=pd.Timestamp("2026-01-01T12:00:00Z"))
    assert result["timestamp"].tolist() == list(pd.to_datetime([
        "2026-01-01T00:00:00Z",
        "2026-01-01T04:00:00Z",
    ]))
    first = result.iloc[0]
    assert first["open"] == 100.0
    assert first["high"] == 105.0
    assert first["low"] == 98.0
    assert first["close"] == 104.0
    assert first["volume"] == 40.0


def test_resample_rejects_unsupported_timeframe():
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        resample_ohlcv(hourly_frame(), "3h")
