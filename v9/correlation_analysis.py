#!/usr/bin/env python3
"""Standalone Bitget 4H historical-return correlation analysis.

This module is intentionally isolated from the V9 signal scanner. It only
uses Bitget USDT-FUTURES symbols for which Bitget returns usable 4H candles.
Outputs CSV correlation matrix and a JSON report under v9/correlation/.
"""
from __future__ import annotations

import csv
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
GRANULARITY = "4H"
INTERVAL_MS = 4 * 60 * 60 * 1000
TIMEOUT = 20
LIMIT = 200
SIX_MONTHS_DAYS = 183
OUTPUT_DIR = Path(os.environ.get("VEGAS_CORRELATION_OUTPUT", "v9/correlation"))
# Snapshot of the stock symbols currently configured in the V9 scanner.
STOCKS = (
    "NVDA","AAPL","MSFT","AMZN","GOOGL","META","TSLA","AVGO","AMD","HOOD",
    "GLW","SPCX","CRCL","MSTR","COIN","PLTR","ORCL","INTC","MU","MRVL",
    "ASML","ARM","APP","RDDT","NFLX","BABA","JD","QCOM","TXN","AMAT",
    "LRCX","KLAC","JPM","GS","BAC","WFC","XOM","CVX","CAT","GE","CEG",
    "UBER","DASH","SHOP","CRM","NOW","PANW","CRWD","TSM"
)

def api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "VEGAS-V9-Correlation/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != "00000":
        raise RuntimeError(f"Bitget API error {payload.get('code')}: {payload.get('msg', 'unknown')}")
    return payload

def available_symbols() -> set[str]:
    payload = api_get("/api/v2/mix/market/contracts", {"productType": PRODUCT_TYPE})
    return {str(row.get("symbol", "")) for row in payload.get("data", []) if row.get("symbol")}

def fetch_4h_candles(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """Fetch up to six months using Bitget's bounded candle pages."""
    all_rows: dict[int, float] = {}
    cursor_end = end_ms
    for _ in range(12):  # 12 x 200 bars comfortably spans six months of 4H bars.
        params = {
            "symbol": symbol, "productType": PRODUCT_TYPE,
            "granularity": GRANULARITY, "limit": str(LIMIT),
            "startTime": str(start_ms), "endTime": str(cursor_end),
        }
        payload = api_get("/api/v2/mix/market/candles", params)
        rows = payload.get("data") or []
        parsed: list[tuple[int, float]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts, close = int(row[0]), float(row[4])
            except (TypeError, ValueError, IndexError):
                continue
            if start_ms <= ts <= end_ms and math.isfinite(close) and close > 0 and ts + INTERVAL_MS <= int(time.time() * 1000):
                parsed.append((ts, close))
        if not parsed:
            break
        before = len(all_rows)
        for ts, close in parsed:
            all_rows[ts] = close
        oldest = min(ts for ts, _ in parsed)
        if oldest <= start_ms or len(rows) < LIMIT or len(all_rows) == before:
            break
        cursor_end = oldest - 1
        time.sleep(0.12)
    return sorted(all_rows.items())

def pearson(x: list[float], y: list[float]) -> float | None:
    n = min(len(x), len(y))
    if n < 30:
        return None
    x, y = x[-n:], y[-n:]
    mx, my = sum(x) / n, sum(y) / n
    dx, dy = [v - mx for v in x], [v - my for v in y]
    denom = math.sqrt(sum(v*v for v in dx) * sum(v*v for v in dy))
    if denom == 0:
        return None
    return sum(a*b for a, b in zip(dx, dy)) / denom

def main() -> int:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - SIX_MONTHS_DAYS * 24 * 60 * 60 * 1000
    end_ms = now_ms - now_ms % INTERVAL_MS
    wanted = [f"{s}USDT" for s in STOCKS]
    try:
        listed = available_symbols()
    except Exception as exc:
        raise SystemExit(f"Cannot query Bitget futures contract list: {exc}")
    candle_map: dict[str, dict[int, float]] = {}
    excluded: list[dict[str, str]] = []
    for symbol in wanted:
        if symbol not in listed:
            excluded.append({"symbol": symbol, "reason": "Not listed on Bitget USDT-FUTURES"})
            continue
        try:
            rows = fetch_4h_candles(symbol, start_ms, end_ms)
            if len(rows) < 30:
                excluded.append({"symbol": symbol, "reason": f"Insufficient usable closed 4H candles ({len(rows)})"})
                continue
            candle_map[symbol] = dict(rows)
            print(f"{symbol}: {len(rows)} closed 4H candles", flush=True)
        except Exception as exc:
            excluded.append({"symbol": symbol, "reason": f"4H data fetch failed: {exc}"})
        time.sleep(0.12)

    # Use exact shared timestamps for each pair; do not forward-fill missing bars.
    symbols = sorted(candle_map)
    returns: dict[str, dict[int, float]] = {}
    for symbol, prices in candle_map.items():
        ts_sorted = sorted(prices)
        returns[symbol] = {
            ts_sorted[i]: prices[ts_sorted[i]] / prices[ts_sorted[i-1]] - 1
            for i in range(1, len(ts_sorted))
            if ts_sorted[i] - ts_sorted[i-1] == INTERVAL_MS and prices[ts_sorted[i-1]] > 0
        }

    matrix: dict[str, dict[str, float | None]] = {}
    pairs: list[dict[str, Any]] = []
    for a in symbols:
        matrix[a] = {}
        for b in symbols:
            common = sorted(set(returns[a]) & set(returns[b]))
            corr = pearson([returns[a][t] for t in common], [returns[b][t] for t in common])
            matrix[a][b] = round(corr, 4) if corr is not None else None
            if a < b and corr is not None:
                pairs.append({"symbol_a": a, "symbol_b": b, "correlation": round(corr, 4), "shared_4h_returns": len(common)})

    pairs.sort(key=lambda p: p["correlation"], reverse=True)
    # Greedy correlation groups: attach a symbol to the group with highest
    # average correlation when that average is >= 0.60; otherwise start a group.
    groups: list[list[str]] = []
    for symbol in symbols:
        best_idx, best_avg = None, -2.0
        for idx, group in enumerate(groups):
            vals = [matrix[symbol].get(other) for other in group]
            vals = [v for v in vals if v is not None]
            avg = sum(vals) / len(vals) if vals else -2.0
            if avg >= 0.60 and avg > best_avg:
                best_idx, best_avg = idx, avg
        if best_idx is None:
            groups.append([symbol])
        else:
            groups[best_idx].append(symbol)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "correlation_matrix.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", *symbols])
        for symbol in symbols:
            writer.writerow([symbol, *[matrix[symbol][s] for s in symbols]])
    report = {
        "source": "Bitget Mix USDT-FUTURES",
        "granularity": GRANULARITY,
        "window_start_utc": datetime.fromtimestamp(start_ms / 1000, timezone.utc).isoformat(),
        "window_end_utc": datetime.fromtimestamp(end_ms / 1000, timezone.utc).isoformat(),
        "method": "Pearson correlation of consecutive 4H close-to-close returns; pairwise exact timestamp intersection; no forward-fill",
        "available_symbols_count": len(symbols),
        "available_symbols": symbols,
        "excluded_count": len(excluded),
        "excluded": excluded,
        "groups_threshold_average_correlation": 0.60,
        "groups": [{"group": i + 1, "symbols": group} for i, group in enumerate(groups)],
        "strongest_pairs": pairs[:100],
        "correlation_matrix_file": "correlation_matrix.csv",
    }
    (OUTPUT_DIR / "correlation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source": report["source"], "granularity": GRANULARITY,
        "available_symbols_count": len(symbols), "excluded_count": len(excluded),
        "groups": report["groups"], "strongest_pairs": pairs[:20],
        "outputs": [str(OUTPUT_DIR / "correlation_report.json"), str(OUTPUT_DIR / "correlation_matrix.csv")]
    }, ensure_ascii=False, indent=2))
    return 0 if symbols else 1

if __name__ == "__main__":
    raise SystemExit(main())
