"""Run the shared V3 Vegas engine over the fixed A-share 4H session candles."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "v3"))

import pandas as pd
from akshare_market_data import AShareDataError, fetch_symbol_4h_history
from bitget_market_data import ema
from notification_digest import ConfirmedSignal, format_digest, load_daily_state, save_daily_state, send_ntfy, update_daily_digest
from signal_system_v3 import Candle, WatchState, evaluate_candle

TZ = ZoneInfo("Asia/Shanghai")


def scan_symbol(name: str, code: str):
    # Same history requirement, EMA calculation, state machine, red-peak
    # observation trigger, midline direction, and EMA12 confirmation as V3.
    bars = fetch_symbol_4h_history(code)
    closes = [bar.close for bar in bars]
    ema12 = ema(closes, 12)
    ema144 = ema(closes, 144)
    ema169 = ema(closes, 169)
    ema576 = ema(closes, 576)
    ema676 = ema(closes, 676)
    watch = WatchState()
    events = []
    for index, bar in enumerate(bars):
        values = (ema12[index], ema144[index], ema169[index], ema576[index], ema676[index])
        if any(value is None for value in values):
            continue
        candle = Candle(close=bar.close, high=bar.high, low=bar.low, closed=bar.closed)
        event = evaluate_candle(
            "4H", candle, float(values[0]), float(values[1]), float(values[2]),
            watch, float(values[3]), float(values[4])
        )
        if event:
            candle_time = datetime.combine(bar.session_date, datetime.min.time(), TZ).isoformat()
            events.append(ConfirmedSignal.from_closed_candle(
                symbol=f"{name}({code})",
                direction=event.direction,
                timeframe="4H",
                candle_time=candle_time,
                close=event.close,
            ))
    last = bars[-1]
    print(
        f"PASS {code} {name}: session_bars={len(bars)} "
        f"latest={last.session_date} close={last.close:g} "
        f"EMA12={ema12[-1]:g} EMA144={ema144[-1]:g} EMA169={ema169[-1]:g} "
        f"EMA576={ema576[-1]:g} EMA676={ema676[-1]:g}"
    )
    return events


def main():
    universe = json.loads((ROOT / "universe.json").read_text(encoding="utf-8"))
    timezone = TZ
    today = datetime.now(timezone).date()
    found, errors = [], []
    print(f"V3 A-share scan local_day={today.isoformat()} timezone=Asia/Shanghai timeframe=4H")
    for item in universe["symbols"]:
        code, name = item["code"], item["name"]
        try:
            events = scan_symbol(name, code)
            found.extend(event for event in events
                         if datetime.fromisoformat(event.candle_time).date() == today)
        except Exception as exc:
            errors.append(f"{code} {name}: {type(exc).__name__}: {exc}")
            print(f"FAIL {code} {name}: {type(exc).__name__}: {exc}")

    state_path = ROOT / ".state" / "notifications.json"
    state = load_daily_state(state_path, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    if errors:
        message += "\n\n行情扫描错误：\n" + "\n".join(errors)
    send_ntfy(message)
    save_daily_state(state_path, state)
    print(f"SCAN_TOTAL={len(universe['symbols'])}")
    print(f"SCAN_ERRORS={len(errors)}")
    print(f"SCAN_SIGNALS_TODAY={len(found)}")
    print(f"SCAN_NEW_SIGNALS={len(new_events)}")
    print("PASS: shared V3 engine notification sent")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
