"""VEGAS V9 grouped notifications via ntfy and Bark."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from typing import Any

def display_symbol(symbol: str) -> str:
    value=symbol.strip().upper()
    if value.endswith("USDT"): value=value[:-4]
    return "CL" if value=="CLU" else value

def send_notification(report_path: str) -> int:
    topic=os.environ.get("V9_NTFY_TOPIC","").strip(); bark_key=os.environ.get("V9_BARK_KEY","").strip(); token=os.environ.get("V9_NTFY_TOKEN","").strip()
    if not topic or not bark_key:
        print("ERROR: V9_NTFY_TOPIC and V9_BARK_KEY must be configured.",file=sys.stderr); return 1
    with open(report_path,encoding="utf-8") as f: report: dict[str,Any]=json.load(f)
    signals=[x for x in report.get("signals",[]) if isinstance(x,dict) and x.get("formal_signal") is True]
    symbols=[]; seen=set()
    for s in signals:
        symbol=display_symbol(str(s.get("symbol","")))
        if symbol and symbol not in seen: symbols.append(symbol); seen.add(symbol)
    if not symbols:
        print("No formal signals found; no notification sent."); return 0
    core_order=["BTC","HYPE","XAU","CL","SNDK"]
    stock_order=["NVDA","AAPL","MSFT","AMZN","GOOGL","META","TSLA","AVGO","AMD","HOOD","GLW","SPCX","CRCL","MSTR","COIN","PLTR","ORCL","INTC","MU","MRVL","ASML","ARM","APP","RDDT","NFLX","BABA","JD","QCOM","TXN","AMAT","LRCX","KLAC","JPM","GS","BAC","WFC","XOM","CVX","CAT","GE","CEG","UBER","DASH","SHOP","CRM","NOW","PANW","CRWD","TSM"]
    core=[s for s in core_order if s in seen]; stocks=[s for s in stock_order if s in seen]; known=set(core_order)|set(stock_order); stocks.extend(s for s in symbols if s not in known)
    parts=["VEGAS V9 SIGNAL SYSTEM"]
    if stocks: parts.append("🔔 美股巨头\n"+"\n".join("   ".join(f"▰ {s} ▰" for s in stocks[i:i+3]) for i in range(0,len(stocks),3)))
    if core: parts.append("🔔 核心能源\n"+"   ".join(f"▰ {s} ▰" for s in core))
    message="\n\n".join(parts); test=os.environ.get("V9_NOTIFICATION_TEST_MODE")=="1"
    if test: message="【测试推送】\n"+message
    ntfy_payload=json.dumps({"topic":topic,"message":message,"priority":4},ensure_ascii=False).encode()
    headers={"Content-Type":"application/json; charset=utf-8"}
    if token: headers["Authorization"]=f"Bearer {token}"
    ntfy_ok=False; bark_ok=False
    try:
        req=urllib.request.Request("https://ntfy.sh/",data=ntfy_payload,headers=headers,method="POST")
        with urllib.request.urlopen(req,timeout=20) as response:
            if not 200<=response.status<300: raise RuntimeError(f"ntfy HTTP {response.status}")
            ntfy_ok=True; print(f"ntfy accepted notification (HTTP {response.status}).")
    except (urllib.error.URLError,TimeoutError,RuntimeError,OSError) as exc: print(f"ntfy failed: {exc}",file=sys.stderr)
    bark_body=message
    if test and bark_body.startswith("【测试推送】\n"): bark_body=bark_body[len("【测试推送】\n"):]
    if bark_body.startswith("VEGAS V9 SIGNAL SYSTEM"): bark_body=bark_body[len("VEGAS V9 SIGNAL SYSTEM"):].lstrip("\n")
    payload=json.dumps({"device_key":bark_key,"title":"【测试推送】VEGAS V9 SIGNAL SYSTEM" if test else "VEGAS V9 SIGNAL SYSTEM","body":bark_body,"group":"VEGAS V9","level":"active"},ensure_ascii=False).encode()
    try:
        req=urllib.request.Request("https://api.day.app/push",data=payload,headers={"Content-Type":"application/json; charset=utf-8"},method="POST")
        with urllib.request.urlopen(req,timeout=20) as response:
            if not 200<=response.status<300: raise RuntimeError(f"Bark HTTP {response.status}")
            bark_ok=True; print(f"Bark accepted notification (HTTP {response.status}); symbols: {', '.join(symbols)}.")
    except (urllib.error.URLError,TimeoutError,RuntimeError,OSError) as exc: print(f"Bark failed: {exc}",file=sys.stderr)
    if ntfy_ok and bark_ok: print("Both notification channels succeeded."); return 0
    print("ERROR: one or more notification channels failed.",file=sys.stderr); return 1
if __name__=="__main__": sys.exit(send_notification(sys.argv[1] if len(sys.argv)>1 else "v9/scan-report.json"))
