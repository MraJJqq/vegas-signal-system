"""Independent Bitget USDT-futures data adapter for V6."""
from __future__ import annotations
import json, math, time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE="https://api.bitget.com"
STOCKS=["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","AMD","NFLX","ORCL","CRM","PLTR","INTC","QCOM","MU","ARM","TSM","COIN","MSTR","HOOD","ADBE","IBM"]
FIXED={"BTCUSDT","HYPEUSDT","XAUUSDT","CLUSDT"}
TARGET={f"{x}USDT" for x in STOCKS}|FIXED
FOUR_HOURS_MS=14400000

def get_json(url):
    req=Request(url,headers={"User-Agent":"VegasSignalSystemV6/1.0"})
    for attempt in range(4):
        try:
            with urlopen(req,timeout=15) as r: data=json.loads(r.read().decode())
            if data.get("code")!="00000": raise RuntimeError(f"Bitget API error: {data}")
            return data
        except Exception:
            if attempt==3: raise
            time.sleep(2*(attempt+1))

def discover_symbols():
    url=BASE+"/api/v2/mix/market/contracts?"+urlencode({"productType":"USDT-FUTURES"})
    data=get_json(url).get("data")
    if not isinstance(data,list): raise RuntimeError("Invalid Bitget contract list")
    active={str(x.get("symbol","")).upper() for x in data if x.get("quoteCoin")=="USDT" and str(x.get("symbolStatus","")).lower()=="normal"}
    symbols=sorted(TARGET&active)
    print(f"V6 universe: active={len(symbols)}, unavailable={sorted(TARGET-active)}")
    if not symbols: raise RuntimeError("No configured V6 contracts are currently active on Bitget")
    return symbols

def ema(values,period):
    if len(values)<period: return [None]*len(values)
    out=[None]*len(values); prev=sum(values[:period])/period; out[period-1]=prev; alpha=2/(period+1)
    for i in range(period,len(values)):
        prev=values[i]*alpha+prev*(1-alpha); out[i]=prev
    return out

def fetch_inputs(symbol, now_ms=None):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    params={"symbol":symbol,"productType":"USDT-FUTURES","granularity":"4H","limit":"1000"}
    url=BASE+"/api/v2/mix/market/candles?"+urlencode(params)
    rows=get_json(url).get("data")
    if not isinstance(rows,list): raise RuntimeError(f"{symbol}: invalid candle data")
    parsed=[]
    for r in rows:
        if len(r)<6: continue
        ts=int(r[0]); o,h,l,c=map(float,r[1:5])
        if not all(math.isfinite(v) and v>0 for v in (o,h,l,c)): continue
        if ts+FOUR_HOURS_MS<=now_ms: parsed.append({"timestamp_ms":ts,"open":o,"high":h,"low":l,"close":c})
    parsed.sort(key=lambda x:x["timestamp_ms"])
    closes=[x["close"] for x in parsed]
    series=[ema(closes,p) for p in (12,144,169,576,676)]
    result=[]
    for i,c in enumerate(parsed):
        vals=[s[i] for s in series]
        if all(v is not None for v in vals):
            result.append({**c,"ema12":vals[0],"ema144":vals[1],"ema169":vals[2],"ema576":vals[3],"ema676":vals[4]})
    if not result: raise RuntimeError(f"{symbol}: insufficient 4H history for EMA676")
    return result
