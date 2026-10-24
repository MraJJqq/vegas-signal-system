"""Independent VEGAS V9 A-share signal engine; no imports from v9/."""
from __future__ import annotations
from typing import Any
LINES = (("中锋EMA144",144),("中锋EMA169",169))

def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None]*len(values)
    if len(values)<period: return out
    prev=sum(values[:period])/period; out[period-1]=prev; alpha=2/(period+1)
    for i in range(period,len(values)):
        prev=values[i]*alpha+prev*(1-alpha); out[i]=prev
    return out

def detect_formal_signals(symbol: str, candles: list[dict[str,Any]], state: dict[str,Any]) -> list[dict[str,Any]]:
    closed=sorted((c for c in candles if c.get('closed')),key=lambda c:c['timestamp_ms'])
    if not closed:return []
    closes=[float(c['close']) for c in closed]
    lines={name:ema(closes,n) for name,n in LINES}; filt=ema(closes,12)
    observing=bool(state.get('observing',False)); touched=list(state.get('touched_lines',[])); touch=state.get('touch_timestamp_ms'); last=int(state.get('last_processed_timestamp_ms',-1)); signals=[]
    for i,c in enumerate(closed):
        ts=int(c['timestamp_ms'])
        if ts<=last:continue
        fv=filt[i]; high=float(c['high']); low=float(c['low']); close=float(c['close'])
        if observing and fv is not None:
            side='上方' if close>fv else '下方' if close<fv else None
            if side:
                signals.append({'formal_signal':True,'symbol':symbol,'timeframe':'1H','line':', '.join(touched),'touch_timestamp_ms':touch,'filter_line':'EMA12','filter_side':side,'filter_value':fv,'close_price':close,'candle_timestamp_ms':ts})
                observing=False;touched=[];touch=None;last=ts;continue
        if not observing:
            hits=[name for name,_ in LINES if lines[name][i] is not None and low<=lines[name][i]<=high]
            if hits:observing=True;touched=hits;touch=ts
        last=ts
    state.update({'observing':observing,'touched_lines':touched,'touch_timestamp_ms':touch,'last_processed_timestamp_ms':last})
    return signals
