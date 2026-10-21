"""Run V5 over 23 selected stocks plus BTC, HYPE, gold and crude oil."""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

from bitget_market_data_v5 import build_v5_inputs, discover_v5_symbols, fetch_closed_4h_candles
from notification_digest_v5 import (
    ConfirmedSignal, format_digest, load_daily_state, save_daily_state,
    send_serverchan, update_daily_digest,
)
from signal_system_v5 import V5WatchStates, evaluate_candle

# Optional manual override via --symbols or V5_SYMBOLS; default is live Bitget discovery.
DEFAULT_SYMBOLS = ""


def scan_symbol(symbol: str, limit: int):
    candles = fetch_closed_4h_candles(symbol, limit=limit)
    rows = build_v5_inputs(candles)
    if not rows:
        raise RuntimeError(
            f"{symbol}: insufficient closed 4H candles to calculate EMA676 "
            f"(closed candles fetched={len(candles)})."
        )
    states = V5WatchStates.fresh()
    events = []
    for row in rows:
        for event in evaluate_candle(
            "4H", row.candle, row.ema12, row.ema144, row.ema169,
            row.ema576, row.ema676, states,
        ):
            stamp = datetime.fromtimestamp(
                row.timestamp_ms / 1000, tz=ZoneInfo("UTC")
            ).isoformat()
            events.append(ConfirmedSignal.from_closed_candle(
                symbol=symbol, direction=event.direction, timeframe="4H",
                candle_time=stamp,
                close=event.close,
            ))
    last = rows[-1]
    stamp = datetime.fromtimestamp(last.timestamp_ms / 1000, tz=ZoneInfo("UTC")).isoformat()
    return events, (
        f"{symbol}: closed_4h={len(candles)} rows_with_emas={len(rows)} "
        f"latest={stamp} close={last.candle.close:g} EMA12={last.ema12:g} "
        f"EMA144={last.ema144:g} EMA169={last.ema169:g} "
        f"EMA576={last.ema576:g} EMA676={last.ema676:g}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=os.getenv("V5_SYMBOLS", DEFAULT_SYMBOLS), help="Optional override; default uses 23 selected stocks plus BTC/HYPE/XAU/CL")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4, help="Concurrent symbols; keep low to respect Bitget rate limits")
    parser.add_argument("--state", default=os.getenv("V5_STATE_FILE", ".state/v5_notifications.json"))
    parser.add_argument("--timezone", default=os.getenv("V5_TIMEZONE", "Asia/Shanghai"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.symbols.strip():
        symbols = list(dict.fromkeys(
            x.strip().upper() for x in args.symbols.split(",") if x.strip()
        ))
        universe_source = "manual override"
    else:
        symbols = discover_v5_symbols()
        universe_source = "Bitget live contract discovery"
    if not symbols:
        raise SystemExit("No symbols configured after exclusions")
    if not 1 <= args.limit <= 1000:
        raise SystemExit("--limit must be between 1 and 1000")
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    tz = ZoneInfo(args.timezone)
    today = datetime.now(tz).date()
    found, errors = [], []
    workers = min(args.workers, len(symbols))
    print(f"V5 local_day={today.isoformat()} timezone={args.timezone} symbols={len(symbols)} workers={workers} universe={universe_source} timeframe=4H")

    def scan_one(symbol: str):
        try:
            events, status = scan_symbol(symbol, args.limit)
            return symbol, events, status, None
        except Exception as exc:
            return symbol, [], None, str(exc)

    # Bounded concurrency speeds up the scan without flooding Bitget with requests.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for symbol, events, status, error in executor.map(scan_one, symbols):
            if error is not None:
                errors.append(f"{symbol}: {error}")
                print(f"FAIL {symbol}: {error}")
                continue
            print("PASS " + status)
            found.extend(
                e for e in events
                if datetime.fromisoformat(e.candle_time).astimezone(tz).date() == today
            )
    state = load_daily_state(args.state, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    if errors:
        message += "\n\n行情扫描错误：\n" + "\n".join(errors)
    if args.dry_run:
        print("\n" + message)
    else:
        send_serverchan(message)
        print("PASS: V5 Server酱 personal-WeChat digest sent")
    save_daily_state(args.state, state)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
