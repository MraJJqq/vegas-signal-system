"""Run a one-shot V3 scan using live Bitget 4H closed candles.

Usage from the v3 directory:
    python run_v3_scan.py BTCUSDT

This is a manual one-shot scan. It does not run continuously or send notifications.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from bitget_market_data import fetch_v3_inputs
from signal_system_v3 import scan_closed_candles


def main() -> int:
    parser = argparse.ArgumentParser(description="Vegas V3 closed 4H signal scan")
    parser.add_argument("symbol", help="Bitget USDT-FUTURES symbol, e.g. BTCUSDT")
    parser.add_argument("--limit", type=int, default=1000, help="4H candles to fetch (1-1000)")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper()
    print(f"Fetching Bitget {symbol} 4H closed candles...")
    inputs = fetch_v3_inputs(symbol, timeframe="4H", limit_4h=args.limit)
    if not inputs:
        raise SystemExit("FAIL: not enough valid closed 4H candles to calculate EMA676")

    events = scan_closed_candles(
        "4H",
        ((item.candle, item.ema12, item.ema144, item.ema169, item.ema576, item.ema676) for item in inputs),
    )
    latest = inputs[-1]
    timestamp = datetime.fromtimestamp(latest.timestamp_ms / 1000, tz=timezone.utc).isoformat()
    print("PASS: live market data fetched and V3 calculations completed")
    print(f"symbol={symbol} timeframe=4H closed_candles_with_emas={len(inputs)}")
    print(f"latest_closed_candle_utc={timestamp}")
    print(f"close={latest.candle.close:.12g} EMA12={latest.ema12:.12g} EMA144={latest.ema144:.12g} EMA169={latest.ema169:.12g} EMA576={latest.ema576:.12g} EMA676={latest.ema676:.12g}")
    if events:
        event = events[-1]
        print(f"historical_signal_count={len(events)}")
        print(f"latest_historical_signal={event.direction} timeframe={event.timeframe} close={event.close:.12g} EMA12={event.filter_ema:.12g}")
    else:
        print("historical_signal_count=0")
        print("No formal signal found in the fetched candle history; this is not an error.")
    print("NOTE: one-shot scan only; no continuous scheduler or notification is enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
