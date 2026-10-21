"""Public Bitget USDT-futures market data adapter for Vegas Signal System V5.

Fetches closed 4H candles, including older history required for EMA676, and
computes V5 EMA inputs. This module does not change signal rules or notify.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from signal_system_v5 import Candle

BASE_URL = "https://api.bitget.com"
CANDLES_PATH = "/api/v3/market/candles"
CONTRACTS_PATH = "/api/v2/mix/market/contracts"
HISTORY_CANDLES_PATH = "/api/v3/market/history-candles"
PRODUCT_TYPE = "USDT-FUTURES"
FOUR_HOURS_MS = 4 * 60 * 60 * 1000
ALLOWED_TIMEFRAMES = ("4H",)
V5_STOCK_SYMBOLS = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","AMD","NFLX","ORCL","CRM","PLTR","INTC","QCOM","MU","ARM","TSM","COIN","MSTR","HOOD","ADBE","IBM"]
V5_FIXED_SYMBOLS = {"BTCUSDT", "HYPEUSDT", "XAUUSDT", "CLUSDT"}
TARGET_SYMBOLS = {f"{ticker}USDT" for ticker in V5_STOCK_SYMBOLS} | V5_FIXED_SYMBOLS
HISTORY_PAGE_SIZE = 100


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

    @property
    def timestamp_utc(self) -> str:
        return datetime.fromtimestamp(
            self.timestamp_ms / 1000, tz=timezone.utc
        ).isoformat()


@dataclass(frozen=True)
class V5Input:
    timestamp_ms: int
    candle: Candle
    ema12: float
    ema144: float
    ema169: float
    ema576: float
    ema676: float


def _http_get_json(url: str, timeout: float = 10.0) -> dict:
    """GET Bitget JSON with bounded exponential backoff for rate limits/transient errors."""
    request = Request(url, headers={"User-Agent": "VegasSignalSystemV5/1.0"})
    body = ""
    for attempt in range(5):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 4:
                # Bitget rate limits are transient. Back off instead of failing
                # the entire symbol scan on the first 429 response.
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 2.0) if retry_after else 2.0 * (2 ** attempt)
                except (TypeError, ValueError):
                    delay = 2.0 * (2 ** attempt)
                time.sleep(min(delay, 20.0))
                continue
            raise BitgetAPIError(f"Bitget HTTP {exc.code}: {detail[:500]}") from exc
        except Exception as exc:
            if attempt < 4:
                time.sleep(min(1.0 * (2 ** attempt), 12.0))
                continue
            raise BitgetAPIError(f"Bitget request failed: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BitgetAPIError("Bitget returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise BitgetAPIError("Bitget response must be a JSON object")
    if payload.get("code") != "00000":
        if payload.get("code") == "429" and "Too Many" in str(payload.get("msg", "")):
            raise BitgetAPIError("Bitget API rate limit 429 persisted after retries")
        raise BitgetAPIError(
            f"Bitget API error code={payload.get('code')!r}: "
            f"{payload.get('msg', 'unknown error')}"
        )
    return payload



def discover_v5_symbols(request_json: Callable[[str], dict] | None = None) -> list[str]:
    """Discover the configured 23-stock shortlist plus BTC, HYPE, gold and crude oil."""
    fetch_json = request_json or _http_get_json
    url = f"{BASE_URL}{CONTRACTS_PATH}?{urlencode({'productType': PRODUCT_TYPE})}"
    payload = fetch_json(url)
    data = payload.get("data")
    if not isinstance(data, list):
        raise BitgetAPIError("Bitget contracts response data is not a list")
    active: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip().upper()
        if (symbol and symbol.endswith("USDT")
                and item.get("quoteCoin") == "USDT"
                and str(item.get("symbolStatus", "")).lower() == "normal"):
            active.add(symbol)
    symbols = sorted(TARGET_SYMBOLS & active)
    unavailable = sorted(TARGET_SYMBOLS - active)
    listed_stocks = len((TARGET_SYMBOLS & active) - V5_FIXED_SYMBOLS)
    print(f"V5 universe: target_stocks={len(V5_STOCK_SYMBOLS)} listed_stocks={listed_stocks} fixed_assets={sorted(V5_FIXED_SYMBOLS & active)} unavailable_targets={unavailable}")
    if not symbols:
        raise BitgetAPIError("Bitget returned no active symbols from the configured V5 universe")
    return symbols

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
        if not all(math.isfinite(value) for value in values):
            raise BitgetAPIError(f"Non-finite candle row: {row!r}")
        if min(open_price, high, low, close) <= 0:
            raise BitgetAPIError(f"Non-positive price in candle row: {row!r}")
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise BitgetAPIError(f"Invalid OHLC relationship: {row!r}")
        if base_volume < 0 or quote_volume < 0:
            raise BitgetAPIError(f"Negative volume in candle row: {row!r}")
        by_timestamp[timestamp_ms] = MarketCandle(
            timestamp_ms, open_price, high, low, close,
            base_volume, quote_volume
        )
    return [by_timestamp[t] for t in sorted(by_timestamp)]


def fetch_closed_4h_candles(
    symbol: str,
    limit: int = 1000,
    now_ms: int | None = None,
    request_json: Callable[[str], dict] | None = None,
) -> list[MarketCandle]:
    """Fetch recent plus paged older 4H candles; exclude any forming candle."""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    fetch_json = request_json or _http_get_json

    def request_rows(path: str, params: dict) -> list[MarketCandle]:
        query = urlencode(params)
        payload = fetch_json(f"{BASE_URL}{path}?{query}")
        data = payload.get("data")
        if not isinstance(data, list):
            raise BitgetAPIError("Bitget response data is not a list")
        return parse_candle_rows(data)

    common = {
        "category": PRODUCT_TYPE,
        "symbol": normalized_symbol,
        "interval": "4H",
        "type": "market",
    }
    recent = request_rows(CANDLES_PATH, {**common, "limit": str(limit)})
    by_timestamp = {c.timestamp_ms: c for c in recent}
    # The recent-candles endpoint may return fewer candles than requested.
    # Page older history whenever the requested limit is not yet satisfied so
    # EMA676 can be calculated consistently across newer and older contracts.
    if len(by_timestamp) < limit:
        while len(by_timestamp) < limit:
            oldest = min(by_timestamp)
            params = {
                **common,
                "endTime": str(oldest - 1),
                "limit": str(min(HISTORY_PAGE_SIZE, limit - len(by_timestamp))),
            }
            older = request_rows(HISTORY_CANDLES_PATH, params)
            if not older:
                break
            previous_count = len(by_timestamp)
            for candle in older:
                by_timestamp[candle.timestamp_ms] = candle
            if len(by_timestamp) == previous_count:
                break
    candles = [by_timestamp[t] for t in sorted(by_timestamp)]
    closed = [
        candle for candle in candles
        if candle.timestamp_ms + FOUR_HOURS_MS <= now_ms
    ]
    return closed[-limit:]


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


def build_v5_inputs(candles: Iterable[MarketCandle]) -> list[V5Input]:
    """Attach EMA12/144/169/576/676; discard rows before all EMAs exist."""
    ordered = sorted(candles, key=lambda candle: candle.timestamp_ms)
    closes = [c.close for c in ordered]
    ema12 = ema(closes, 12)
    ema144 = ema(closes, 144)
    ema169 = ema(closes, 169)
    ema576 = ema(closes, 576)
    ema676 = ema(closes, 676)
    result: list[V5Input] = []
    for index, candle in enumerate(ordered):
        values = (ema12[index], ema144[index], ema169[index], ema576[index], ema676[index])
        if any(value is None for value in values):
            continue
        result.append(V5Input(
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
            ema576=float(values[3]),
            ema676=float(values[4]),
        ))
    return result


def fetch_v5_inputs(
    symbol: str,
    timeframe: str = "4H",
    limit_4h: int = 1000,
    now_ms: int | None = None,
    request_json: Callable[[str], dict] | None = None,
) -> list[V5Input]:
    """Fetch Bitget 4H data and return inputs ready for V3 evaluation."""
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError("V5 only supports 4H")
    candles = fetch_closed_4h_candles(
        symbol, limit=limit_4h, now_ms=now_ms, request_json=request_json
    )
    return build_v5_inputs(candles)
