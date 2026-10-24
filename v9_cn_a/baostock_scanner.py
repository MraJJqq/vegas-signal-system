"""Independent Baostock-powered VEGAS V9 A-share scanner."""
from __future__ import annotations
import json, os, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import baostock as bs
from vegas_signals_cn import detect_formal_signals

TZ=timezone(timedelta(hours=8))
STATE_PATH=Path(os.environ.get("V9_CN_A_STATE_PATH","v9_cn_a/.signal-state.json"))
REPORT_PATH=Path(os.environ.get("V9_CN_A_REPORT_PATH","v9_cn_a/scan-report.json"))
POOL_PATH=Path(os.environ.get("V9_CN_A_POOL_PATH","v9_cn_a/baostock-stock-pool.json"))
CANDLE_CACHE_PATH=Path(os.environ.get("V9_CN_A_CANDLE_CACHE_PATH","v9_cn_a/.candle-cache.json"))
CACHE_MAX_CANDLES=900
CACHE_REFRESH_DAYS=7

def load_pool():
    data=json.loads(POOL_PATH.read_text(encoding="utf-8"))
    stocks=data.get("stocks",[])
    if len(stocks)!=2000: raise RuntimeError(f"Expected exactly 2000 stocks in {POOL_PATH}; got {len(stocks)}")
    codes=[x.get("code") for x in stocks]
    if len(set(codes))!=2000: raise RuntimeError("Pool contains duplicate stock codes")
    return stocks

def fetch(code:str, cached:list[dict[str,Any]]|None=None)->list[dict[str,Any]]:
    # Keep enough history for EMA676; refresh a short overlap to catch new/corrected bars.
    cached = cached or []
    if cached:
        latest_ms=max(int(x["timestamp_ms"]) for x in cached)
        start=(datetime.fromtimestamp(latest_ms/1000,tz=TZ).date()-timedelta(days=CACHE_REFRESH_DAYS)).isoformat()
    else:
        start=(datetime.now(TZ).date()-timedelta(days=365)).isoformat()
    end=datetime.now(TZ).date().isoformat()
    rs=bs.query_history_k_data_plus(code,"date,time,code,open,high,low,close,volume,amount,adjustflag",start_date=start,end_date=end,frequency="60",adjustflag="3")
    if rs.error_code!="0": raise RuntimeError(f"{rs.error_code}: {rs.error_msg}")
    out=[]
    while rs.next():
        row=dict(zip(rs.fields,rs.get_row_data()))
        try:
            digits="".join(ch for ch in row["time"] if ch.isdigit())
            stamp=datetime.strptime(digits[:14],"%Y%m%d%H%M%S").replace(tzinfo=TZ)
            o,h,lo,c=(float(row[k]) for k in ("open","high","low","close"))
            if min(o,h,lo,c)<=0 or lo>min(o,c) or max(o,c)>h: continue
            ts=int(stamp.timestamp()*1000)
            out.append({"timestamp_ms":ts,"open":o,"high":h,"low":lo,"close":c,"volume":float(row.get("volume") or 0),"closed":ts+3600000<=int(time.time()*1000)})
        except (ValueError,KeyError,TypeError,OverflowError):
            continue
    merged={int(x["timestamp_ms"]):x for x in cached}
    merged.update({int(x["timestamp_ms"]):x for x in out})
    result=sorted(merged.values(),key=lambda x:x["timestamp_ms"])[-CACHE_MAX_CANDLES:]
    if not result: raise ValueError("Baostock returned no valid 1H OHLC candles")
    return result

def send_bark(signals:list[dict[str,Any]])->dict[str,Any]:
    key=os.environ.get("BARK_KEY","").strip()
    if not key: return {"status":"skipped","reason":"BARK_KEY_missing"}
    symbols=[]; seen=set()
    for s in signals:
        sym=str(s.get("symbol","")).strip().upper()
        if sym and sym not in seen: symbols.append(sym); seen.add(sym)
    symbol_lines="\n".join("   ".join(f"▰ {sym} ▰" for sym in symbols[i:i+3]) for i in range(0,len(symbols),3))
    body="🔔 A股\n"+(symbol_lines if symbol_lines else "▰ NOCHANGE ▰")
    payload=json.dumps({"device_key":key,"title":"VEGAS V9 SIGNAL SYSTEM","body":body,"group":"VEGAS V9","level":"active"},ensure_ascii=False).encode()
    req=urllib.request.Request("https://api.day.app/push",data=payload,headers={"Content-Type":"application/json; charset=utf-8"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            body_text=resp.read().decode("utf-8","replace")
            if not 200<=resp.status<300: raise RuntimeError(f"Bark HTTP {resp.status}: {body_text[:200]}")
        try: parsed=json.loads(body_text)
        except json.JSONDecodeError: parsed={}
        if isinstance(parsed,dict) and parsed.get("code") not in (None,200): raise RuntimeError(f"Bark rejected push: {body_text[:200]}")
        return {"status":"sent","signals":len(signals),"symbols":symbols}
    except Exception as exc: return {"status":"failed","error":f"{type(exc).__name__}: {exc}"}

def main()->int:
    today=datetime.now(TZ).date().isoformat()
    pool=load_pool()
    try: state=json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): state={}
    daily=state.get("__daily_formal_signals__",{})
    if daily.get("date")!=today: daily={"date":today,"signals":[]}
    bykey={(s.get("symbol"),s.get("candle_timestamp_ms"),s.get("filter_side")):s for s in daily.get("signals",[]) if isinstance(s,dict)}
    try: candle_cache=json.loads(CANDLE_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): candle_cache={}
    report={"started_at_utc":datetime.now(timezone.utc).isoformat(),"source":"Baostock 60-minute A-share K-line","timeframe":"1H","pool_size":len(pool),"symbols_ok":0,"symbols_excluded":[],"results":[],"new_signals":[],"signals":[]}
    login=bs.login()
    if login.error_code!="0": raise RuntimeError(f"Baostock login failed: {login.error_code} {login.error_msg}")
    try:
        for i,item in enumerate(pool,1):
            code,name=item["code"],item["name"]
            try:
                candles=fetch(code,candle_cache.get(code,[]))
                candle_cache[code]=candles
                symbol=code.replace(".","").upper()
                signals=detect_formal_signals(symbol,candles,state.setdefault(symbol,{}))
                for s in signals:
                    if datetime.fromtimestamp(s["candle_timestamp_ms"]/1000,tz=TZ).date().isoformat()==today:
                        s["name"]=name
                        bykey[(s["symbol"],s["candle_timestamp_ms"],s["filter_side"])]=s
                        report["new_signals"].append(s)
                report["symbols_ok"]+=1
                report["results"].append({"code":code,"name":name,"data_available":True,"candles":len(candles),"latest_closed_candle_ms":max((c["timestamp_ms"] for c in candles if c["closed"]),default=None)})
            except Exception as exc:
                report["symbols_excluded"].append({"code":code,"name":name,"reason":str(exc)})
                report["results"].append({"code":code,"name":name,"data_available":False,"error":str(exc)})
            if i%100==0: print(f"[{i}/2000] data_ok={report['symbols_ok']} excluded={len(report['symbols_excluded'])}")
    finally: bs.logout()
    CANDLE_CACHE_PATH.parent.mkdir(parents=True,exist_ok=True)
    cache_tmp=CANDLE_CACHE_PATH.with_suffix(CANDLE_CACHE_PATH.suffix+".tmp")
    cache_tmp.write_text(json.dumps(candle_cache,separators=(",",":"),ensure_ascii=False),encoding="utf-8"); cache_tmp.replace(CANDLE_CACHE_PATH)
    report["signals"]=list(bykey.values())
    state["__daily_formal_signals__"]={"date":today,"signals":report["signals"]}
    STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE_PATH.with_suffix(STATE_PATH.suffix+".tmp")
    tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(STATE_PATH)
    report["bark_notification"]=send_bark(report["signals"])
    REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="results"},ensure_ascii=False,indent=2))
    return 0 if report["symbols_ok"]>=1600 else 1
if __name__=="__main__": raise SystemExit(main())
