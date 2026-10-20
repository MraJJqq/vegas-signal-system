from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .data import resample_ohlcv
from .indicators import validate_ohlcv


class BitgetMarketDataProvider:
    """Bitget-only public market candles. No alternate-provider fallback."""

    FUTURES_URL = "https://api.bitget.com/api/v2/mix/market/candles"
    SPOT_URL = "https://api.bitget.com/api/v2/spot/market/candles"
    REALITY_STOCKS_URL = "https://api.bitget.com/api/v3/reality/market/stock-info"

    def __init__(self, symbols: list[dict], history_limit: int = 2000, timeout: int = 15):
        self.symbols = {
            str(item["id"]): {
                "symbol": str(item.get("bitget_symbol") or ""),
                "stock_code": str(item.get("bitget_stock_code") or "").upper(),
                "category": str(item.get("bitget_category", "USDT-FUTURES")).upper(),
                "product_type": str(item.get("bitget_product_type", "USDT-FUTURES")),
            }
            for item in symbols
            if item.get("bitget_symbol")
        }
        self.history_limit = max(300, min(int(history_limit), 3000))
        self.timeout = timeout
        self._cache: dict[str, pd.DataFrame] = {}
        self._reality_symbols: dict[str, str] | None = None

    def _request(self, url: str, query: dict) -> dict:
        request = Request(
            f"{url}?{urlencode(query)}",
            headers={"User-Agent": "VegasSignalSystem/1.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != "00000":
            raise ValueError(f"Bitget API error: {payload.get('msg', 'unknown error')}")
        return payload

    def _resolve_reality_symbol(self, stock_code: str) -> str:
        if self._reality_symbols is None:
            payload = self._request(self.REALITY_STOCKS_URL, {})
            self._reality_symbols = {
                str(item.get("code", "")).upper(): str(item.get("symbol", ""))
                for item in payload.get("data", [])
                if item.get("code") and item.get("symbol")
            }
        symbol = self._reality_symbols.get(stock_code, "")
        if not symbol:
            raise ValueError(f"Bitget Reality does not list stock code {stock_code}")
        return symbol

    def _load_hourly(self, symbol_id: str) -> pd.DataFrame:
        if symbol_id in self._cache:
            return self._cache[symbol_id]
        spec = self.symbols.get(symbol_id)
        if not spec:
            raise ValueError(f"No Bitget symbol configured for {symbol_id}; alternate data sources are disabled")
        if not spec["symbol"] and spec["stock_code"]:
            spec["symbol"] = self._resolve_reality_symbol(spec["stock_code"])
            spec["category"] = "SPOT"
        if not spec["symbol"]:
            raise ValueError(f"No Bitget symbol configured for {symbol_id}; alternate data sources are disabled")

        rows = []
        end_time = None
        remaining = self.history_limit
        while remaining > 0:
            batch_size = min(1000, remaining)
            if spec["category"] == "SPOT":
                query = {
                    "category": "SPOT",
                    "symbol": spec["symbol"],
                    "granularity": "1h",
                    "limit": str(batch_size),
                }
                if end_time is not None:
                    query["endTime"] = str(end_time)
                payload = self._request(self.SPOT_URL, query)
            else:
                query = {
                    "symbol": spec["symbol"],
                    "productType": spec["product_type"],
                    "granularity": "1H",
                    "limit": str(batch_size),
                }
                if end_time is not None:
                    query["endTime"] = str(end_time)
                payload = self._request(self.FUTURES_URL, query)

            batch = payload.get("data") or []
            if not batch:
                break
            rows.extend(batch)
            remaining -= len(batch)
            oldest = min(int(row[0]) for row in batch)
            if end_time is not None and oldest >= end_time:
                break
            end_time = oldest - 1
            if len(batch) < batch_size:
                break

        if not rows:
            raise ValueError(f"No Bitget hourly candles returned for {spec['symbol']} ({spec['category']})")

        frame = pd.DataFrame(rows)
        # Bitget candle rows: timestamp, open, high, low, close, volume, quote volume.
        frame = frame.iloc[:, :7]
        frame.columns = ["timestamp", "open", "high", "low", "close", "volume", "quote_volume"]
        frame["timestamp"] = pd.to_datetime(
            pd.to_numeric(frame["timestamp"], errors="coerce"), unit="ms", utc=True
        )
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
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
            raise ValueError(f"No completed {timeframe} Bitget candles available for {symbol_id}")
        return result
