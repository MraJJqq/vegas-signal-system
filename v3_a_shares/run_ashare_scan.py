"""Run the A-share-only V3 scan using the 4H midline and EMA12 filter."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "v3"))

from akshare_market_data import fetch_symbol_4h_history
from bitget_market_data import ema
from notification_digest import ConfirmedSignal, format_digest, load_daily_state, save_daily_state, send_ntfy, update_daily_digest
from signal_system_v3 import Candle, WatchState, evaluate_candle

TZ = ZoneInfo("Asia/Shanghai")


def scan_symbol(name: str, code: str):
    # A-share-specific scope: observe the EMA144/EMA169 midline band only;
    # EMA12 remains the closed-candle confirmation filter. No red-peak EMA576/676.
    bars = fetch_symbol_4h_history(code)
    closes = [bar.close for bar in bars]
    ema12 = ema(closes, 12)
    ema144 = ema(closes, 144)
    ema169 = ema(closes, 169)
    watch = WatchState()
    events = []
    for index, bar in enumerate(bars):
        values = (ema12[index], ema144[index], ema169[index])
        if any(value is None for value in values):
            continue
        candle = Candle(close=bar.close, high=bar.high, low=bar.low, closed=bar.closed)
        event = evaluate_candle(
            "4H", candle, float(values[0]), float(values[1]), float(values[2]), watch
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
        f"EMA12={ema12[-1]:g} EMA144={ema144[-1]:g} EMA169={ema169[-1]:g}"
    )
    return events


def main():
    universe = json.loads((ROOT / "universe.json").read_text(encoding="utf-8"))
    today = datetime.now(TZ).date()
    found, errors = [], []
    scan_total = len(universe["symbols"])
    scan_successes = 0
    print(f"V3 A-share scan local_day={today.isoformat()} timezone=Asia/Shanghai timeframe=4H indicators=EMA144,EMA169,EMA12 red_peak=OFF")
    for item in universe["symbols"]:
        code, name = item["code"], item["name"]
        try:
            events = scan_symbol(name, code)
            scan_successes += 1
            found.extend(event for event in events
                         if datetime.fromisoformat(event.candle_time).date() == today)
        except Exception as exc:
            errors.append(f"{code} {name}: {type(exc).__name__}: {exc}")
            print(f"FAIL {code} {name}: {type(exc).__name__}: {exc}")

    print(f"SCAN_TOTAL={scan_total}")
    print(f"SCAN_SUCCESSES={scan_successes}")
    print(f"SCAN_ERRORS={len(errors)}")
    print(f"SCAN_SIGNALS_TODAY={len(found)}")

    # Never publish a formal-signal notification from an incomplete scan.
    if errors or scan_successes != scan_total:
        print("SCAN_ABORTED_INCOMPLETE=1; no notification sent; digest state unchanged")
        raise SystemExit(1)

    state_path = ROOT / ".state" / "notifications.json"
    state = load_daily_state(state_path, today)
    state, new_events = update_daily_digest(state, found, today)
    message = format_digest(state, new_events)
    send_ntfy(message)
    save_daily_state(state_path, state)
    print(f"SCAN_NEW_SIGNALS={len(new_events)}")
    print("PASS: complete A-share scan finished and notification sent")

if __name__ == "__main__":
    main()
