"""VEGAS V7 Bitget market-data scanner.

This module only retrieves and validates Bitget USDT perpetual 4H candles.
It deliberately does not emit trading signals until the approved V7 rule
implementation is added; data availability is not a trading signal.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from vegas_signals import detect_formal_signals

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
# User-confirmed rule: scan 4H candles only. Do not add other timeframes without approval.
GRANULARITIES = ("4H",)
CANDLE_LIMIT = 800
REQUEST_TIMEOUT = 15

# User-confirmed final V7 scan pool: 23 US stocks plus BTC, HYPE, gold and crude oil.
# These are Bitget USDT contract symbols; do not expand or substitute the list.
STOCKS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "AMD", "NFLX", "ORCL", "CRM", "PLTR", "INTC", "QCOM", "MU",
    "ARM", "TSM", "COIN", "MSTR", "HOOD", "ADBE", "IBM",
)
OTHER_MARKETS = ("BTC", "HYPE", "XAU", "CLU")
SYMBOLS = tuple(f"{ticker}USDT" for ticker in (*STOCKS, *OTHER_MARKETS))


class BitgetError(RuntimeError):
    pass


def _get_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VEGAS-V7/1.0", "Accept": "application/json"},
    )
    # One request only: no automatic retries or repeated polling.
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise BitgetError(f"Request failed (no retry): {exc}") from exc
    if payload.get("code") != "00000":
        raise BitgetError(
            f"Bitget API error code={payload.get('code')}: "
            f"{payload.get('msg', 'unknown error')}"
        )
    return payload


def fetch_candles(symbol: str, granularity: str, limit: int = CANDLE_LIMIT) -> list[dict[str, Any]]:
    payload = _get_json(
        "/api/v2/mix/market/candles",
        {
            "symbol": symbol,
            "productType": PRODUCT_TYPE,
            "granularity": granularity,
            "limit": str(limit),
        },
    )
    rows = payload.get("data") or []
    candles: list[dict[str, Any]] = []
    for row in rows:
        # Bitget Mix candle format: [ts, open, high, low, close, baseVol, quoteVol, usdtVol]
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            candle = {
                "timestamp_ms": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "closed": False,
            }
        except (TypeError, ValueError, IndexError):
            continue
        candles.append(candle)

    candles.sort(key=lambda item: item["timestamp_ms"])
    now_ms = int(time.time() * 1000)
    interval_ms = _granularity_ms(granularity)
    for candle in candles:
        candle["closed"] = candle["timestamp_ms"] + interval_ms <= now_ms
    return candles


def _granularity_ms(granularity: str) -> int:
    if granularity.endswith("H"):
        return int(granularity[:-1]) * 60 * 60 * 1000
    if granularity.endswith("m"):
        return int(granularity[:-1]) * 60 * 1000
    raise ValueError(f"Unsupported candle granularity: {granularity}")


def ema(values: list[float], period: int) -> list[float | None]:
    """Return EMA values aligned to input; warm-up entries are None."""
    if period < 1:
        raise ValueError("EMA period must be >= 1")
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


def scan_market_data() -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "started_at_utc": started,
        "source": "Bitget Mix USDT-FUTURES",
        "scan_timeframes": list(GRANULARITIES),
        "symbols_total": len(SYMBOLS),
        "symbols_ok": 0,
        "symbols_excluded": 0,
        "results": [],
        "signals": [],
        "note": "4H market-data scan only; EMA12 filter values are calculated for closed candles, but formal signal logic remains disabled.",
    }
    for symbol in SYMBOLS:
        item: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
        symbol_complete = True
        for timeframe in GRANULARITIES:
            try:
                candles = fetch_candles(symbol, timeframe)
                closed = [c for c in candles if c["closed"]]
                report["signals"].extend(detect_formal_signals(symbol, candles))
                if not closed:
                    symbol_complete = False
                closes = [c["close"] for c in closed]
                ema12_values = ema(closes, 12)
                latest_ema12 = ema12_values[-1] if ema12_values else None
                latest_close = closes[-1] if closes else None
                item["timeframes"][timeframe] = {
                    "candles_received": len(candles),
                    "closed_candles": len(closed),
                    "latest_closed_candle_ms": closed[-1]["timestamp_ms"] if closed else None,
                    "latest_closed_price": latest_close,
                    "ema12_filter": latest_ema12,
                    "close_vs_ema12": (
                        "above" if latest_close > latest_ema12 else
                        "below" if latest_close < latest_ema12 else
                        "equal" if latest_close == latest_ema12 else None
                    ) if latest_close is not None and latest_ema12 is not None else None,
                }
            except Exception as exc:
                symbol_complete = False
                item["timeframes"][timeframe] = {"error": str(exc)}
        item["data_available"] = symbol_complete
        item["excluded_reason"] = None if symbol_complete else "Missing/insufficient closed 4H candle data"
        report["results"].append(item)
        if symbol_complete:
            report["symbols_ok"] += 1
        else:
            report["symbols_excluded"] += 1
    return report


def main() -> int:
    report = scan_market_data()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    output_path = os.environ.get("V7_REPORT_PATH")
    if output_path:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(rendered + "\n")
    # Fail the job only if no symbol returned any usable closed candles.
    return 0 if report["symbols_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
