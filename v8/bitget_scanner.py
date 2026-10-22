"""VEGAS V8 Bitget USDT-futures scanner."""
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
GRANULARITY = "4H"
CANDLE_LIMIT = 800
REQUEST_TIMEOUT = 15

# Final pool: core markets first, then selected US stock contracts.
CORE_MARKETS = ("BTC", "HYPE", "XAU", "CLU", "SNDK")
STOCKS = (
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META",
    "TSLA", "AVGO", "AMD", "HOOD", "GLW", "SPCX",
)
SYMBOLS = tuple(f"{ticker}USDT" for ticker in (*CORE_MARKETS, *STOCKS))


class BitgetError(RuntimeError):
    pass


def get_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VEGAS-V8/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise BitgetError(f"Bitget request failed: {exc}") from exc
    if payload.get("code") != "00000":
        raise BitgetError(f"Bitget API error {payload.get('code')}: {payload.get('msg', 'unknown')}")
    return payload


def fetch_candles(symbol: str) -> list[dict[str, Any]]:
    payload = get_json(
        "/api/v2/mix/market/candles",
        {
            "symbol": symbol,
            "productType": PRODUCT_TYPE,
            "granularity": GRANULARITY,
            "limit": str(CANDLE_LIMIT),
        },
    )
    candles: list[dict[str, Any]] = []
    for row in payload.get("data") or []:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            candles.append({
                "timestamp_ms": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "closed": False,
            })
        except (TypeError, ValueError, IndexError):
            continue
    candles.sort(key=lambda c: c["timestamp_ms"])
    now_ms = int(time.time() * 1000)
    interval_ms = 4 * 60 * 60 * 1000
    for candle in candles:
        candle["closed"] = candle["timestamp_ms"] + interval_ms <= now_ms
    return candles


def scan_market_data() -> dict[str, Any]:
    report: dict[str, Any] = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Bitget Mix USDT-FUTURES",
        "scan_timeframes": [GRANULARITY],
        "symbols_total": len(SYMBOLS),
        "symbols_ok": 0,
        "symbols_excluded": 0,
        "results": [],
        "signals": [],
    }
    for symbol in SYMBOLS:
        item: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
        try:
            candles = fetch_candles(symbol)
            closed = [c for c in candles if c["closed"]]
            if not closed:
                raise BitgetError("No closed 4H candles returned")
            report["signals"].extend(detect_formal_signals(symbol, candles))
            item["timeframes"][GRANULARITY] = {
                "candles_received": len(candles),
                "closed_candles": len(closed),
                "latest_closed_candle_ms": closed[-1]["timestamp_ms"],
                "latest_closed_price": closed[-1]["close"],
            }
            item["data_available"] = True
            item["excluded_reason"] = None
            report["symbols_ok"] += 1
        except Exception as exc:
            item["timeframes"][GRANULARITY] = {"error": str(exc)}
            item["data_available"] = False
            item["excluded_reason"] = str(exc)
            report["symbols_excluded"] += 1
        report["results"].append(item)
    return report


def main() -> int:
    report = scan_market_data()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    output_path = os.environ.get("V8_REPORT_PATH", "v8/scan-report.json")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(rendered + "\n")
    return 0 if report["symbols_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
