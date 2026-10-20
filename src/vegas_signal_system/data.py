from __future__ import annotations

from pathlib import Path

import pandas as pd

from .indicators import validate_ohlcv


TIMEFRAME_HOURS = {"1h": 1, "2h": 2, "4h": 4, "8h": 8}


class CsvMarketDataProvider:
    """Local CSV provider for development and repeatable tests.

    Expected path: data_dir/{symbol_id}_{timeframe}.csv, e.g. GOLD_4h.csv.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load(self, symbol_id: str, timeframe: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol_id}_{timeframe}.csv"
        if not path.exists():
            raise FileNotFoundError(f"No market data file: {path}")
        return validate_ohlcv(pd.read_csv(path))


def resample_ohlcv(hourly: pd.DataFrame, timeframe: str, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Resample 1-hour bars and remove bars whose full timeframe has not closed."""
    if timeframe not in TIMEFRAME_HOURS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    frame = validate_ohlcv(hourly)
    hours = TIMEFRAME_HOURS[timeframe]
    if hours == 1:
        result = frame
    else:
        indexed = frame.set_index("timestamp")
        result = indexed.resample(
            f"{hours}h", label="left", closed="left", origin="start_day"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna(subset=["open", "high", "low", "close"]).reset_index()
    current = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    result = result[result["timestamp"] + pd.Timedelta(hours=hours) <= current]
    return validate_ohlcv(result) if not result.empty else result.reset_index(drop=True)

