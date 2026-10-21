"""V3 scan orchestration. Vegas rules remain in signal_system_v3.py."""
import argparse
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bitget_market_data import fetch_v3_inputs
from notification_digest import ConfirmedSignal, format_digest, load_daily_state, save_daily_state, send_ntfy, update_daily_digest
from signal_system_v3 import WatchState, evaluate_candle


def scan_symbol(symbol, limit):
    rows = fetch_v3_inputs(symbol, timeframe="4H", limit_4h=limit)
    if not rows:
        raise RuntimeError(f"{symbol}: insufficient closed 4H candles for EMA676")
    watch = WatchState()
    events = []
    for row in rows:
        event = evaluate_candle("4H", row.candle, row.ema12, row.ema144, row.ema169, watch, row.ema576, row.ema676)
        if event:
            ts = datetime.fromtimestamp(row.timestamp_ms / 1000, tz=ZoneInfo("UTC")).isoformat()
            events.append(ConfirmedSignal.from_closed_candle(
                symbol=symbol, direction=event.direction, timeframe="4H",
                candle_time=ts, close=event.close))
    last = rows[-1]
    ts = datetime.fromtimestamp(last.timestamp_ms / 1000, tz=ZoneInfo("UTC")).isoformat()
    return events, (f"{symbol}: closed_4h={len(rows)} latest={ts} close={last.candle.close:g} "
        f"EMA12={last.ema12:g} EMA144={last.ema144:g} EMA169={last.ema169:g} "
        f"EMA576={last.ema576:g} EMA676={last.ema676:g}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=os.getenv("V3_SYMBOLS", "XAUUSDT,CLUUSDT,HYPEUSDT"))
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--state", default=os.getenv("V3_STATE_FILE", ".state/notifications.json"))
    p.add_argument("--timezone", default=os.getenv("V3_TIMEZONE", "Asia/Shanghai"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    symbols = list(dict.fromkeys(s.strip().upper() for s in a.symbols.split(",") if s.strip()))
    if not symbols:
        raise SystemExit("No symbols configured")
    if not 1 <= a.limit <= 1000:
        raise SystemExit("--limit must be between 1 and 1000")
    tz = ZoneInfo(a.timezone)
    today = datetime.now(tz).date()
    found, errors = [], []
    print(f"V3 local_day={today.isoformat()} timezone={a.timezone} symbols={','.join(symbols)} timeframe=4H")
    for symbol in symbols:
        try:
            events, status = scan_symbol(symbol, a.limit)
            print("PASS " + status)
            found.extend(e for e in events if datetime.fromisoformat(e.candle_time).astimezone(tz).date() == today)
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
            print(f"FAIL {symbol}: {exc}")
    state = load_daily_state(a.state, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    if errors:
        message += "\n\n行情扫描错误：\n" + "\n".join(errors)
    if a.dry_run:
        print("\n" + message)
    else:
        send_ntfy(message)
        print("PASS: ntfy digest sent")
    save_daily_state(a.state, state)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
