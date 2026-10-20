"""Minimal public Bitget USDT-futures candle adapter for V2.

Uses Bitget only. It deliberately does not fall back to other data providers.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.bitget.com"
GRANULARITY = {"1h": "1H", "2h": "2H", "4h": "4H"}
SECONDS = {"1h": 3600, "2h": 7200, "4h": 14400}


class BitgetAPIError(RuntimeError):
    pass


class BitgetCandleProvider:
    def __init__(self, history_limit: int = 600, timeout: int = 15):
        self.history_limit = max(200, min(int(history_limit), 1000))
        self.timeout = timeout

    def load(self, symbol: str, timeframe: str) -> list[dict]:
        tf = timeframe.lower()
        if tf not in GRANULARITY:
            raise ValueError(f"Unsupported V2 timeframe: {timeframe}")
        params = urlencode({
            "symbol": symbol.upper(),
            "productType": "USDT-FUTURES",
            "granularity": GRANULARITY[tf],
            "limit": str(self.history_limit),
        })
        request = Request(
            f"{BASE_URL}/api/v2/mix/market/history-candles?{params}",
            headers={"Accept": "application/json", "User-Agent": "VegasSignalV2/2.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BitgetAPIError(f"{symbol} {tf}: Bitget request failed: {exc}") from exc
        if payload.get("code") != "00000":
            raise BitgetAPIError(
                f"{symbol} {tf}: Bitget API code={payload.get('code')} "
                f"message={payload.get('msg', '')}"
            )
        raw_rows = payload.get("data") or []
        if not isinstance(raw_rows, list):
            raise BitgetAPIError(f"{symbol} {tf}: malformed candle payload")
        now_ms = int(time.time() * 1000)
        duration_ms = SECONDS[tf] * 1000
        candles = []
        for row in raw_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                continue
            try:
                ts = int(row[0])
                candle = {
                    "timestamp_ms": ts,
                    "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                    "open": float(row[1]), "high": float(row[2]),
                    "low": float(row[3]), "close": float(row[4]),
                    "volume": float(row[5]) if len(row) > 5 else 0.0,
                    "complete": ts + duration_ms <= now_ms,
                    "symbol": symbol.upper(), "timeframe": tf,
                }
            except (TypeError, ValueError, OverflowError):
                continue
            if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
                continue
            if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
                continue
            candles.append(candle)
        candles.sort(key=lambda item: item["timestamp_ms"])
        # De-duplicate timestamps defensively and keep only validated records.
        unique = {item["timestamp_ms"]: item for item in candles}
        return list(unique.values())
