"""Public Bitget USDT-futures market data adapter for Vegas Signal System V3.

This module fetches closed 4H candles and derives 8H candles from pairs of
consecutive, UTC-aligned 4H candles because Bitget's Mix candle endpoint does
not list native 8H granularity. It computes only the V3 EMA12/EMA144/EMA169
inputs; it does not change signal rules or send notifications.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from signal_system_v3 import Candle

BASE_URL = "https://api.bitget.com"
CANDLES_PATH = "/api/v2/mix/market/candles"
PRODUCT_TYPE = "USDT-FUTURES"
FOUR_HOURS_MS = 4 * 60 * 60 * 1000
EIGHT_HOURS_MS = 8 * 60 * 60 * 1000
ALLOWED_TIMEFRAMES = ("4H", "8H")


class BitgetAPIError(RuntimeError):
    """Raised when Bitget returns an API error or an invalid response."""


@dataclass(frozen=True)
class MarketCandle:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    quote_volume: float
    synthetic: bool = False

    @property
    def timestamp_utc(self) -> str:
        return datetime.fromtimestamp(
            self.timestamp_ms / 1000, tz=timezone.utc
        ).isoformat()


@dataclass(frozen=True)
class V3Input:
    timestamp_ms: int
    candle: Candle
    ema12: float
    ema144: float
    ema169: float
    synthetic: bool = False


def _http_get_json(url: str, timeout: float = 10.0) -> dict:
    request = Request(url, headers={"User-Agent": "VegasSignalSystemV3/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except Exception as exc:
        raise BitgetAPIError(f"Bitget request failed: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BitgetAPIError("Bitget returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise BitgetAPIError("Bitget response must be a JSON object")
    if payload.get("code") != "00000":
        raise BitgetAPIError(
            f"Bitget API error code={payload.get('code')!r}: "
            f"{payload.get('msg', 'unknown error')}"
        )
    return payload


def parse_candle_rows(rows: Iterable[list]) -> list[MarketCandle]:
    """Parse Bitget [timestamp, open, high, low, close, baseVol, quoteVol] rows."""
    by_timestamp: dict[int, MarketCandle] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise BitgetAPIError(f"Malformed candle row: {row!r}")
        try:
            timestamp_ms = int(row[0])
            open_price, high, low, close = map(float, row[1:5])
            base_volume = float(row[5])
            quote_volume = float(row[6]) if len(row) > 6 else 0.0
        except (TypeError, ValueError, OverflowError) as exc:
            raise BitgetAPIError(f"Non-numeric candle row: {row!r}") from exc
        values = (open_price, high, low, close, base_volume, quote_volume)
        if not all(__import__("math").isfinite(value) for value in values):
            raise BitgetAPIError(f"Non-finite candle row: {row!r}")
        if min(open_price, high, low, close) <= 0:
            raise BitgetAPIError(f"Non-positive price in candle row: {row!r}")
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise BitgetAPIError(f"Invalid OHLC relationship: {row!r}")
        if base_volume < 0 or quote_volume < 0:
            raise BitgetAPIError(f"Negative volume in candle row: {row!r}")
        by_timestamp[timestamp_ms] = MarketCandle(
            timestamp_ms, open_price, high, low, close,
            base_volume, quote_volume, False
        )
    return [by_timestamp[t] for t in sorted(by_timestamp)]


def fetch_closed_4h_candles(
    symbol: str,
    limit: int = 1000,
    now_ms: int | None = None,
    request_json: Callable[[str], dict] | None = None,
) -> list[MarketCandle]:
    """Fetch recent 4H candles and exclude the currently forming candle."""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    query = urlencode({
        "symbol": normalized_symbol,
        "productType": PRODUCT_TYPE,
        "granularity": "4H",
        "limit": str(limit),
    })
    fetch_json = request_json or _http_get_json
    payload = fetch_json(f"{BASE_URL}{CANDLES_PATH}?{query}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise BitgetAPIError("Bitget response data is not a list")
    candles = parse_candle_rows(data)
    closed = [
        candle for candle in candles
        if candle.timestamp_ms + FOUR_HOURS_MS <= now_ms
    ]
    return closed[-limit:]


def aggregate_8h_from_4h(candles: Iterable[MarketCandle]) -> list[MarketCandle]:
    """Aggregate only complete, consecutive, UTC-aligned 4H pairs into 8H."""
    ordered = sorted(candles, key=lambda candle: candle.timestamp_ms)
    by_timestamp = {c.timestamp_ms: c for c in ordered}
    buckets: dict[int, list[MarketCandle]] = {}
    for candle in ordered:
        bucket_start = (candle.timestamp_ms // EIGHT_HOURS_MS) * EIGHT_HOURS_MS
        buckets.setdefault(bucket_start, []).append(candle)

    result: list[MarketCandle] = []
    for bucket_start in sorted(buckets):
        expected = (bucket_start, bucket_start + FOUR_HOURS_MS)
        first = by_timestamp.get(expected[0])
        second = by_timestamp.get(expected[1])
        if first is None or second is None:
            continue
        # Require exact UTC bucket alignment and do not bridge missing bars.
        result.append(MarketCandle(
            timestamp_ms=bucket_start,
            open=first.open,
            high=max(first.high, second.high),
            low=min(first.low, second.low),
            close=second.close,
            base_volume=first.base_volume + second.base_volume,
            quote_volume=first.quote_volume + second.quote_volume,
            synthetic=first.synthetic or second.synthetic,
        ))
    return result


def ema(values: list[float], period: int) -> list[float | None]:
    """EMA seeded with the first period's simple moving average."""
    if period < 1:
        raise ValueError("period must be >= 1")
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    seed = sum(values[:period]) / period
    output[period - 1] = seed
    alpha = 2.0 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = values[index] * alpha + previous * (1.0 - alpha)
        output[index] = previous
    return output


def build_v3_inputs(candles: Iterable[MarketCandle]) -> list[V3Input]:
    """Attach EMA12/144/169 to candles; discard rows before all EMAs exist."""
    ordered = sorted(candles, key=lambda candle: candle.timestamp_ms)
    closes = [c.close for c in ordered]
    ema12 = ema(closes, 12)
    ema144 = ema(closes, 144)
    ema169 = ema(closes, 169)
    result: list[V3Input] = []
    for index, candle in enumerate(ordered):
        values = (ema12[index], ema144[index], ema169[index])
        if any(value is None for value in values):
            continue
        result.append(V3Input(
            timestamp_ms=candle.timestamp_ms,
            candle=Candle(
                close=candle.close,
                high=candle.high,
                low=candle.low,
                closed=True,
            ),
            ema12=float(values[0]),
            ema144=float(values[1]),
            ema169=float(values[2]),
            synthetic=candle.synthetic,
        ))
    return result


def fetch_v3_inputs(
    symbol: str,
    timeframe: str,
    limit_4h: int = 1000,
    now_ms: int | None = None,
    request_json: Callable[[str], dict] | None = None,
) -> list[V3Input]:
    """Fetch recent Bitget data and return inputs ready for V3 evaluation.

    For 8H, the source data is 4H candles aggregated into exact UTC-aligned
    pairs. Gaps are not silently filled; incomplete 8H pairs are omitted.
    """
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError("V3 only supports 4H and 8H")
    candles_4h = fetch_closed_4h_candles(
        symbol, limit=limit_4h, now_ms=now_ms, request_json=request_json
    )
    candles = candles_4h if timeframe == "4H" else aggregate_8h_from_4h(candles_4h)
    return build_v3_inputs(candles)
