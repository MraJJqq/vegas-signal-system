"""One-shot A-share 4H Vegas scan for the fixed 24-symbol pool."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import akshare as ak

from akshare_market_data import AShareDataError, aggregate_session_4h

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")


def fetch_history(code: str):
    end = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    # The 4H Vegas scan only needs EMA12/144/169 history, not EMA676.
    df = ak.stock_zh_a_hist_min_em(
        symbol=code,
        start_date="2020-01-01 09:30:00",
        end_date=end,
        period="60",
        adjust="qfq",
    )
    bars = aggregate_session_4h(code, df)
    if len(bars) < 200:
        raise AShareDataError(f"{code}: usable 4H session bars insufficient ({len(bars)})")
    return bars


def evaluate(name: str, code: str):
    bars = fetch_history(code)
    frame = pd.DataFrame([{
        "date": b.session_date,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
    } for b in bars]).sort_values("date").reset_index(drop=True)
    # EMA values use only closed 4H session candles.
    for period in (12, 144, 169):
        frame[f"ema{period}"] = frame["close"].ewm(span=period, adjust=False).mean()
    last = frame.iloc[-1]
    # Formal signal only when the latest completed 4H candle touches either
    # midline (EMA144 or EMA169) and closes on a defined EMA12 side.
    touched = any(float(last["low"]) <= float(last[f"ema{p}"]) <= float(last["high"])
                  for p in (144, 169))
    if not touched:
        return None
    close, filter_line = float(last["close"]), float(last["ema12"])
    if close > filter_line:
        direction = "▲"
    elif close < filter_line:
        direction = "▼"
    else:
        return None
    return {"code": code, "name": name, "direction": direction,
            "date": str(last["date"]), "close": close}


def notify(signals):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not signals:
        print("SCAN_RESULT=NO_FORMAL_SIGNALS")
        return
    if not topic:
        raise RuntimeError("NTFY_TOPIC secret is missing; cannot send signal notification")
    body = "\n".join(f"{s['name']} {s['direction']}" for s in signals)
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": "VEGAS V3 A股", "Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        print(f"NTFY_HTTP_STATUS={response.status}")
        if not 200 <= response.status < 300:
            raise RuntimeError(f"ntfy returned HTTP {response.status}")
    print("PUSHED_SIGNALS=" + json.dumps(signals, ensure_ascii=False))


def main():
    universe = json.loads((ROOT / "universe.json").read_text(encoding="utf-8"))
    signals, errors = [], []
    print(f"SCAN_STARTED={datetime.now(TZ).isoformat()}")
    for item in universe["symbols"]:
        code, name = item["code"], item["name"]
        try:
            result = evaluate(name, code)
            print(f"{code} {name}: " + ("SIGNAL " + result["direction"] if result else "NO_SIGNAL"))
            if result:
                signals.append(result)
        except Exception as exc:
            errors.append((code, str(exc)))
            print(f"{code} {name}: ERROR {type(exc).__name__}: {exc}")
    print(f"SCAN_TOTAL={len(universe['symbols'])}")
    print(f"SCAN_ERRORS={len(errors)}")
    print(f"SCAN_SIGNAL_COUNT={len(signals)}")
    notify(signals)
    if errors:
        print("SCAN_ERRORS_DETAIL=" + json.dumps(errors, ensure_ascii=False))


if __name__ == "__main__":
    main()
