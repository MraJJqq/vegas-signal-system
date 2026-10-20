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


class YahooFinanceMarketDataProvider:
    """Optional Yahoo Finance provider with per-symbol caching.

    Yahoo symbols are proxies, not guaranteed to match a broker's exact instrument.
    Intraday history availability and upstream service stability are not guaranteed.
    """

    def __init__(self, symbols: list[dict], history_period: str = "60d"):
        self.symbols = {str(item["id"]): str(item["provider_symbol"]) for item in symbols if item.get("provider_symbol")}
        self.history_period = history_period
        self._cache: dict[str, pd.DataFrame] = {}

    def _load_hourly(self, symbol_id: str) -> pd.DataFrame:
        if symbol_id in self._cache:
            return self._cache[symbol_id]
        if symbol_id not in self.symbols:
            raise ValueError(f"No provider_symbol configured for {symbol_id}")
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError('Yahoo provider requires installation with: pip install -e ".[market-data]"') from exc

        ticker = self.symbols[symbol_id]
        raw = yf.download(
            ticker,
            period=self.history_period,
            interval="1h",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if raw is None or raw.empty:
            raise ValueError(f"No hourly market data returned for {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.rename_axis("timestamp").reset_index()
        rename = {column: str(column).lower() for column in raw.columns}
        raw = raw.rename(columns=rename)
        if "datetime" in raw.columns and "timestamp" not in raw.columns:
            raw = raw.rename(columns={"datetime": "timestamp"})
        required = ["timestamp", "open", "high", "low", "close"]
        missing = [column for column in required if column not in raw.columns]
        if missing:
            raise ValueError(f"Yahoo data missing columns: {', '.join(missing)}")
        if "volume" not in raw.columns:
            raw["volume"] = 0
        # Ignore the current unfinished hourly candle.
        current_hour = pd.Timestamp.now(tz="UTC").floor("h")
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True, errors="coerce")
        raw = raw[raw["timestamp"] < current_hour]
        frame = validate_ohlcv(raw[["timestamp", "open", "high", "low", "close", "volume"]])
        self._cache[symbol_id] = frame
        return frame

    def load(self, symbol_id: str, timeframe: str) -> pd.DataFrame:
        hourly = self._load_hourly(symbol_id)
        result = resample_ohlcv(hourly, timeframe)
        if result.empty:
            raise ValueError(f"No completed {timeframe} candles available for {symbol_id}")
        return result
