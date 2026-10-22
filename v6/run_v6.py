"""V6 scanner. Observation state is rebuilt from today's closed candles."""
from __future__ import annotations
import json, os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from bitget_market_data_v6 import discover_symbols, fetch_inputs
from signal_system_v6 import Candle, WatchStates, evaluate_candle
from notification_v6 import format_signal_digest, send_wechat

TZ=ZoneInfo("Asia/Shanghai")
STATE_PATH=Path(os.getenv("V6_STATE_FILE",".state/v6_daily_state.json"))

def scan_symbol(symbol, today, already_sent):
    rows=fetch_inputs(symbol)
    local_rows=[r for r in rows if datetime.fromtimestamp(r["timestamp_ms"]/1000,TZ).date().isoformat()==today]
    watches=WatchStates()
    events=[]
    for row in local_rows:
        found=evaluate_candle(Candle(row["close"],row["high"],row["low"],True),
            row["ema12"],row["ema144"],row["ema169"],row["ema576"],row["ema676"],watches)
        for event in found:
            event_id=f'{symbol}|{event.observation}|{row["timestamp_ms"]}|{event.direction}'
            if event_id not in already_sent:
                events.append({"id":event_id,"symbol":symbol,"direction":event.direction,
                    "observation":event.observation,"close":event.close,"candle_time":row["timestamp_ms"]})
    return symbol,events,watches

def main():
    today=datetime.now(TZ).date().isoformat()
    symbols=discover_symbols()
    state={"day":today,"sent_ids":[]}
    if STATE_PATH.exists():
        try:
            old=json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if old.get("day")==today: state=old
        except (OSError,json.JSONDecodeError):
            print("V6 state unreadable; starting fresh daily state")
    sent=set(state.get("sent_ids",[]))
    errors=[]; results=[]
    with ThreadPoolExecutor(max_workers=min(4,len(symbols))) as pool:
        futures={pool.submit(scan_symbol,symbol,today,sent):symbol for symbol in symbols}
        for future,symbol in [(f,futures[f]) for f in futures]:
            try:
                result=future.result(); results.append(result)
                _,events,watches=result
                print(f"PASS {symbol}: new_formal_signals={len(events)} watch_midline={watches.midline} watch_red_peak={watches.red_peak}")
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
                print(f"FAIL {symbol}: {exc}")
    new_events=[event for _,events,_ in results for event in events]
    if new_events:
        send_wechat(format_signal_digest(new_events))
        sent.update(event["id"] for event in new_events)
        print(f"V6 formal signal notification sent: {len(new_events)} event(s)")
    else:
        print("V6: no formal signals; no notification sent")
    STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    STATE_PATH.write_text(json.dumps({"day":today,"sent_ids":sorted(sent)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if errors:
        print("V6 scan errors:\n"+"\n".join(errors))
        return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
