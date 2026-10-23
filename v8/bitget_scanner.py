"""VEGAS V8 Bitget USDT-futures scanner."""
from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any

from vegas_signals import detect_formal_signals

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
GRANULARITY = "1H"
CANDLE_LIMIT = 800
REQUEST_TIMEOUT = 15
SIGNAL_STATE_PATH = os.environ.get("V8_SIGNAL_STATE_PATH", "v8/.signal-state.json")

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
    seen_timestamps: set[int] = set()
    for candle in candles:
        timestamp_ms = candle["timestamp_ms"]
        if timestamp_ms in seen_timestamps:
            raise BitgetError(f"Duplicate candle timestamp: {timestamp_ms}")
        seen_timestamps.add(timestamp_ms)
        prices = [candle[key] for key in ("open", "high", "low", "close")]
        if not all(math.isfinite(value) and value > 0 for value in prices):
            raise BitgetError(f"Invalid OHLC value at {timestamp_ms}")
        if candle["high"] < max(candle["open"], candle["close"]):
            raise BitgetError(f"High below open/close at {timestamp_ms}")
        if candle["low"] > min(candle["open"], candle["close"]):
            raise BitgetError(f"Low above open/close at {timestamp_ms}")
        if candle["low"] > candle["high"]:
            raise BitgetError(f"Low above high at {timestamp_ms}")
    now_ms = int(time.time() * 1000)
    interval_ms = 60 * 60 * 1000
    for candle in candles:
        candle["closed"] = candle["timestamp_ms"] + interval_ms <= now_ms
    return candles


def load_signal_state() -> dict[str, dict[str, Any]]:
    try:
        with open(SIGNAL_STATE_PATH, "r", encoding="utf-8") as file:
            value = json.load(file)
        if not isinstance(value, dict):
            return {}
        return {str(symbol): state for symbol, state in value.items() if isinstance(state, dict)}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_signal_state(state: dict[str, dict[str, Any]]) -> None:
    directory = os.path.dirname(SIGNAL_STATE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary_path = SIGNAL_STATE_PATH + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, SIGNAL_STATE_PATH)


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
    signal_state = load_signal_state()
    for symbol in SYMBOLS:
        item: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
        try:
            candles = fetch_candles(symbol)
            closed = [c for c in candles if c["closed"]]
            if not closed:
                raise BitgetError("No closed 1H candles returned")
            # Only keep signals from closed 1H candles dated today in China time.
            china_tz = timezone(timedelta(hours=8))
            china_today = datetime.now(china_tz).date()
            symbol_state = signal_state.setdefault(symbol, {})
            daily_signals = detect_formal_signals(symbol, candles, symbol_state)
            report["signals"].extend(
                signal for signal in daily_signals
                if datetime.fromtimestamp(
                    signal["candle_timestamp_ms"] / 1000, tz=china_tz
                ).date() == china_today
            )
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
    save_signal_state(signal_state)
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
