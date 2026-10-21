"""Standalone V6 scan runner: Bitget closed 4H candles -> Vegas signals -> ntfy digest."""
from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from bitget_market_data_v6 import discover_v6_symbols, fetch_v6_inputs
from notification_digest_v6 import ConfirmedSignal, format_digest, load_daily_state, save_daily_state, send_ntfy, update_daily_digest
from signal_system_v6 import V6WatchStates, evaluate_candle

def scan_symbol(symbol: str, limit: int):
    rows = fetch_v6_inputs(symbol, timeframe="4H", limit_4h=limit)
    if not rows:
        raise RuntimeError(f"{symbol}: insufficient closed 4H history for EMA676")
    states = V6WatchStates.fresh()
    events = []
    for row in rows:
        for event in evaluate_candle("4H", row.candle, row.ema12, row.ema144, row.ema169, row.ema576, row.ema676, states):
            stamp = datetime.fromtimestamp(row.timestamp_ms / 1000, tz=ZoneInfo("UTC")).isoformat()
            events.append(ConfirmedSignal.from_closed_candle(symbol=symbol, direction=event.direction, timeframe="4H", candle_time=stamp, close=event.close))
    last = rows[-1]
    return events, f"{symbol}: rows={len(rows)} latest_close={last.candle.close:g} EMA12={last.ema12:g}"

def main() -> int:
    from argparse import ArgumentParser
    p = ArgumentParser()
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--state", default=os.getenv("V6_STATE_FILE", ".state/v6_notifications.json"))
    p.add_argument("--timezone", default=os.getenv("V6_TIMEZONE", "Asia/Shanghai"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not 676 <= args.limit <= 1000: raise SystemExit("--limit must be between 676 and 1000 for EMA676")
    if not 1 <= args.workers <= 8: raise SystemExit("--workers must be between 1 and 8")
    tz = ZoneInfo(args.timezone); today = datetime.now(tz).date()
    symbols = discover_v6_symbols()
    found, errors = [], []
    def one(symbol):
        try: return symbol, *scan_symbol(symbol, args.limit), None
        except Exception as exc: return symbol, [], None, str(exc)
    with ThreadPoolExecutor(max_workers=min(args.workers, len(symbols))) as pool:
        for symbol, events, status, error in pool.map(one, symbols):
            if error: errors.append(f"{symbol}: {error}"); print(f"FAIL {symbol}: {error}"); continue
            print("PASS " + status)
            found.extend(e for e in events if datetime.fromisoformat(e.candle_time).astimezone(tz).date() == today)
    state = load_daily_state(args.state, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    if errors: message += "\n\n行情扫描错误：\n" + "\n".join(errors)
    if args.dry_run: print(message)
    else: send_ntfy(message); print("PASS: V6 ntfy request accepted")
    save_daily_state(args.state, state)
    return 1 if errors else 0

if __name__ == "__main__": raise SystemExit(main())