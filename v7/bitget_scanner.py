"""VEGAS V7 Bitget market-data scanner.

This module only retrieves and validates Bitget USDT perpetual candles.
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

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
GRANULARITIES = ("1H", "2H", "4H", "8H")
CANDLE_LIMIT = 200
REQUEST_TIMEOUT = 15
RETRY_COUNT = 3

# Confirmed V5 stock universe (Bitget USDT contract symbols), plus the
# previously specified BTC, HYPE, gold and crude-oil markets.
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
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("code") != "00000":
                raise BitgetError(
                    f"Bitget API error code={payload.get('code')}: "
                    f"{payload.get('msg', 'unknown error')}"
                )
            return payload
        except Exception as exc:
            last_error = exc
            if attempt + 1 < RETRY_COUNT:
                time.sleep(1.5 * (attempt + 1))
    raise BitgetError(f"Request failed: {last_error}") from last_error


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


def scan_market_data() -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "started_at_utc": started,
        "source": "Bitget Mix USDT-FUTURES",
        "symbols_total": len(SYMBOLS),
        "symbols_ok": 0,
        "symbols_failed": 0,
        "results": [],
        "signals": [],
        "note": "Market-data scan only; formal signal logic is not enabled in this build.",
    }
    for symbol in SYMBOLS:
        item: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
        symbol_ok = False
        for timeframe in GRANULARITIES:
            try:
                candles = fetch_candles(symbol, timeframe)
                closed = [c for c in candles if c["closed"]]
                if closed:
                    symbol_ok = True
                item["timeframes"][timeframe] = {
                    "candles_received": len(candles),
                    "closed_candles": len(closed),
                    "latest_closed_candle_ms": closed[-1]["timestamp_ms"] if closed else None,
                    "latest_closed_price": closed[-1]["close"] if closed else None,
                }
            except Exception as exc:
                item["timeframes"][timeframe] = {"error": str(exc)}
        item["data_available"] = symbol_ok
        report["results"].append(item)
        if symbol_ok:
            report["symbols_ok"] += 1
        else:
            report["symbols_failed"] += 1
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
