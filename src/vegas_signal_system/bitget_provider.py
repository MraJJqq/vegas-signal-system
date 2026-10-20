from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .data import resample_ohlcv
from .indicators import validate_ohlcv


class BitgetMarketDataProvider:
    """Public Bitget USDT-futures candles; no API key required for market data."""

    BASE_URL = "https://api.bitget.com/api/v2/mix/market/candles"

    def __init__(self, symbols: list[dict], history_limit: int = 200, timeout: int = 15):
        self.symbols = {
            str(item["id"]): {
                "symbol": str(item.get("bitget_symbol") or item.get("provider_symbol") or ""),
                "product_type": str(item.get("bitget_product_type", "USDT-FUTURES")),
            }
            for item in symbols
            if item.get("bitget_symbol") or item.get("provider_symbol")
        }
        self.history_limit = max(50, min(int(history_limit), 1000))
        self.timeout = timeout
        self._cache: dict[str, pd.DataFrame] = {}

    def _load_hourly(self, symbol_id: str) -> pd.DataFrame:
        if symbol_id in self._cache:
            return self._cache[symbol_id]
        spec = self.symbols.get(symbol_id)
        if not spec or not spec["symbol"]:
            raise ValueError(f"No Bitget symbol configured for {symbol_id}")
        params = urlencode({
            "symbol": spec["symbol"],
            "productType": spec["product_type"],
            "granularity": "1H",
            "limit": str(min(self.history_limit, 1000)),
        })
        request = Request(
            f"{self.BASE_URL}?{params}",
            headers={"User-Agent": "VegasSignalSystem/1.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != "00000":
            raise ValueError(f"Bitget API error for {spec['symbol']}: {payload.get('msg', 'unknown error')}")
        rows = payload.get("data") or []
        if not rows:
            raise ValueError(f"No Bitget hourly candles returned for {spec['symbol']}")
        frame = pd.DataFrame(rows, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "quote_volume"
        ])
        frame["timestamp"] = pd.to_datetime(pd.to_numeric(frame["timestamp"], errors="coerce"), unit="ms", utc=True)
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        # Exclude the currently forming 1H candle to avoid repainting / premature signals.
        current_hour = pd.Timestamp.now(tz="UTC").floor("h")
        frame = frame[frame["timestamp"] + pd.Timedelta(hours=1) <= current_hour]
        frame = frame[["timestamp", "open", "high", "low", "close", "volume"]]
        frame = validate_ohlcv(frame.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True))
        if frame.empty:
            raise ValueError(f"No completed Bitget hourly candles available for {spec['symbol']}")
        self._cache[symbol_id] = frame
        return frame

    def load(self, symbol_id: str, timeframe: str) -> pd.DataFrame:
        hourly = self._load_hourly(symbol_id)
        result = resample_ohlcv(hourly, timeframe)
        if result.empty:
            raise ValueError(f"No completed {timeframe} candles available for {symbol_id}")
        return result
