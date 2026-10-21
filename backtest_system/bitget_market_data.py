"""Bitget USDT-FUTURES historical candle downloader for V1.

Uses Bitget's public market-data endpoint. This module downloads and validates
closed candles only; it does not generate or alter Vegas signals.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.bitget.com"
HISTORY_PATH = "/api/v2/mix/market/history-candles"
PRODUCT_TYPE = "USDT-FUTURES"

# Bitget granularity names; values are milliseconds.
TIMEFRAME_MS = {
    "1H": 60 * 60 * 1000,
    "2H": 2 * 60 * 60 * 1000,
    "4H": 4 * 60 * 60 * 1000,
    "8H": 8 * 60 * 60 * 1000,
    "6H": 6 * 60 * 60 * 1000,
    "12H": 12 * 60 * 60 * 1000,
    "1D": 24 * 60 * 60 * 1000,
}


@dataclass(frozen=True)
class HistoricalCandle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    quote_volume: float
    is_synthetic: bool = False


class BitgetMarketDataError(RuntimeError):
    """Raised when Bitget returns an error or malformed candle data."""


def _parse_candle(symbol: str, timeframe: str, row: list) -> HistoricalCandle:
    if len(row) < 6:
        raise BitgetMarketDataError(f"Malformed Bitget candle row: {row!r}")
    try:
        ts = int(row[0])
        o, h, low, c = (float(row[i]) for i in range(1, 5))
        base_volume = float(row[5])
        quote_volume = float(row[6]) if len(row) > 6 else 0.0
    except (TypeError, ValueError, IndexError) as exc:
        raise BitgetMarketDataError(f"Invalid Bitget candle row: {row!r}") from exc
    if not (all(map(lambda x: x == x and abs(x) != float("inf"), (o, h, low, c, base_volume, quote_volume)))):
        raise BitgetMarketDataError(f"Non-finite values in candle row: {row!r}")
    if min(o, h, low, c) <= 0 or h < max(o, c, low) or low > min(o, c, h):
        raise BitgetMarketDataError(f"Invalid OHLC values in candle row: {row!r}")
    return HistoricalCandle(
        symbol=symbol.upper(),
        timeframe=timeframe,
        timestamp=datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
        open=o, high=h, low=low, close=c,
        base_volume=base_volume, quote_volume=quote_volume,
    )


def fetch_history_candles(
    symbol: str = "XAUUSDT",
    timeframe: str = "4H",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
    pause_seconds: float = 0.05,
) -> list[HistoricalCandle]:
    """Fetch candles between start and end (UTC), oldest first.

    Bitget's history endpoint returns up to 200 rows per request. The newest
    still-open candle is always excluded. The caller should pass timezone-aware
    datetimes for start/end; omitted end means current UTC time.
    """
    symbol = symbol.upper().strip()
    timeframe = timeframe.upper().strip()
    if not symbol:
        raise ValueError("symbol must not be empty")
    if timeframe not in TIMEFRAME_MS:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; choose {sorted(TIMEFRAME_MS)}")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    end = end or datetime.now(timezone.utc)
    start = start or datetime.fromtimestamp(0, timezone.utc)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start/end must be timezone-aware")
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    if start_ms >= end_ms:
        raise ValueError("start must be earlier than end")

    step = TIMEFRAME_MS[timeframe]
    # A closed candle's opening time must be no later than end - timeframe.
    latest_closed_open_ms = (end_ms // step) * step - step
    cursor_end = min(end_ms, latest_closed_open_ms + step - 1)
    all_rows: dict[int, HistoricalCandle] = {}

    while cursor_end >= start_ms:
        params = urlencode({
            "symbol": symbol,
            "productType": PRODUCT_TYPE,
            "granularity": timeframe,
            "startTime": max(start_ms, cursor_end - step * (limit - 1)),
            "endTime": cursor_end,
            "limit": limit,
        })
        request = Request(
            f"{BASE_URL}{HISTORY_PATH}?{params}",
            headers={"User-Agent": "VEGAS-V1-backtest/1.0", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BitgetMarketDataError(f"Bitget request failed: {exc}") from exc

        if payload.get("code") != "00000":
            raise BitgetMarketDataError(
                f"Bitget API error code={payload.get('code')}: {payload.get('msg', 'unknown error')}"
            )
        rows = payload.get("data") or []
        if not rows:
            break

        parsed = [_parse_candle(symbol, timeframe, row) for row in rows]
        parsed.sort(key=lambda candle: candle.timestamp)
        oldest_ms = int(parsed[0].timestamp.timestamp() * 1000)
        for candle in parsed:
            ts_ms = int(candle.timestamp.timestamp() * 1000)
            if start_ms <= ts_ms <= latest_closed_open_ms:
                all_rows[ts_ms] = candle
        if oldest_ms <= start_ms or oldest_ms >= cursor_end:
            break
        cursor_end = oldest_ms - 1
        if pause_seconds:
            time.sleep(pause_seconds)

    return [all_rows[ts] for ts in sorted(all_rows)]


def candles_to_csv_rows(candles: Iterable[HistoricalCandle]) -> list[dict[str, str]]:
    """Convert candles to stable CSV-friendly dictionaries."""
    return [{
        "symbol": c.symbol,
        "timeframe": c.timeframe,
        "timestamp": c.timestamp.isoformat(),
        "open": str(c.open), "high": str(c.high),
        "low": str(c.low), "close": str(c.close),
        "base_volume": str(c.base_volume),
        "quote_volume": str(c.quote_volume),
        "is_synthetic": str(c.is_synthetic).lower(),
    } for c in candles]
