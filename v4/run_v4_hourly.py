"""Run the V4 hourly Bitget 4H scan and ntfy daily digest."""
import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from bitget_market_data_v4 import build_v4_inputs, fetch_closed_4h_candles
from notification_digest_v4 import (
    ConfirmedSignal, format_digest, load_daily_state, save_daily_state,
    send_ntfy, update_daily_digest,
)
from signal_system_v4 import WatchState, evaluate_candle


def scan_symbol(symbol: str, limit: int):
    candles = fetch_closed_4h_candles(symbol, limit=limit)
    rows = build_v4_inputs(candles)
    if not rows:
        raise RuntimeError(
            f"{symbol}: insufficient closed 4H candles to calculate EMA676 "
            f"(closed candles fetched={len(candles)})."
        )
    watch = WatchState()
    events = []
    for row in rows:
        event = evaluate_candle(
            "4H", row.candle, row.ema12, row.ema144, row.ema169,
            watch, row.ema576, row.ema676,
        )
        if event:
            stamp = datetime.fromtimestamp(row.timestamp_ms / 1000, tz=ZoneInfo("UTC")).isoformat()
            events.append(ConfirmedSignal.from_closed_candle(
                symbol=symbol, direction=event.direction, timeframe="4H",
                candle_time=stamp, close=event.close,
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
    parser.add_argument("--symbols", default=os.getenv(
        "V4_SYMBOLS",
        "SPYUSDT,QQQUSDT,SNDKUSDT,NVDAUSDT,AMDUSDT,AVGOUSDT,MUUSDT,TSMUSDT,"
        "MSFTUSDT,AAPLUSDT,TSLAUSDT,ARMUSDT,AMZNUSDT,METAUSDT,GOOGLUSDT,"
        "ORCLUSDT,PLTRUSDT,COINUSDT,MSTRUSDT,HOODUSDT,XAUUSDT,CLUSDT,BTCUSDT,HYPEUSDT"
    ))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--state", default=os.getenv("V4_STATE_FILE", ".state/notifications.json"))
    parser.add_argument("--timezone", default=os.getenv("V4_TIMEZONE", "Asia/Shanghai"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    symbols = list(dict.fromkeys(x.strip().upper() for x in args.symbols.split(",") if x.strip()))
    if not symbols:
        raise SystemExit("No symbols configured")
    if not 1 <= args.limit <= 1000:
        raise SystemExit("--limit must be between 1 and 1000")
    tz = ZoneInfo(args.timezone)
    today = datetime.now(tz).date()
    found, errors = [], []
    print(f"V4 local_day={today.isoformat()} timezone={args.timezone} symbols={len(symbols)} timeframe=4H")
    for symbol in symbols:
        try:
            events, status = scan_symbol(symbol, args.limit)
            print("PASS " + status)
            found.extend(e for e in events if datetime.fromisoformat(e.candle_time).astimezone(tz).date() == today)
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
            print(f"FAIL {symbol}: {exc}")
    state = load_daily_state(args.state, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    if errors:
        message += "\n\n行情扫描错误：\n" + "\n".join(errors)
    if args.dry_run:
        print("\n" + message)
    else:
        send_ntfy(message)
        print("PASS: V4 ntfy digest sent")
    save_daily_state(args.state, state)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
