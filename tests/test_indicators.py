import pandas as pd
import pytest

from vegas_signal_system.indicators import add_indicators, classify_direction, validate_ohlcv


def sample_frame(n=180):
    close = [100 + i * 0.5 for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
        "open": close,
        "high": [x + 1 for x in close],
        "low": [x - 1 for x in close],
        "close": close,
        "volume": [10] * n,
    })


def test_validate_ohlcv_sorts_and_deduplicates():
    frame = sample_frame(4).iloc[[2, 0, 1, 1]].copy()
    result = validate_ohlcv(frame)
    assert len(result) == 3
    assert result["timestamp"].is_monotonic_increasing


def test_validate_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        validate_ohlcv(pd.DataFrame({"close": [1]}))


def test_indicators_and_up_direction():
    config = {"indicators": {"filter_sma": 2, "entry_ema": 3, "direction_ema": 5, "direction_ema_alternative": 6, "major_ema": 10}}
    result = add_indicators(sample_frame(30), config)
    assert "ema_5" in result.columns
    assert classify_direction(result, 5) == "up"
