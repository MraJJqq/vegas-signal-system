"""Validate native Tencent 4H (m240) K-lines; never substitute daily/hourly data."""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

CONFIG = Path(__file__).with_name("ashare_universe.json")
ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TIMEOUT_SECONDS = 15

def market_symbol(code: str) -> str:
    return ("sh" if code.startswith(("5", "6", "9")) else "sz") + code

def fetch_period(symbol: str, period: str, start: date, end: date) -> dict:
    params = {"param": f"{symbol},{period},{start.isoformat()},{end.isoformat()},200,qfq"}
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; VEGAS-V8-Tencent-4H-Test/1.0)",
        "Referer": "https://finance.qq.com/",
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")
    match = re.search(r"\\{.*\\}", raw, flags=re.S)
    if not match:
        raise ValueError(f"response is not JSON/JSONP (body length={len(raw)})")
    payload = json.loads(match.group(0))
    node = (payload.get("data") or {}).get(symbol)
    if not isinstance(node, dict):
        raise ValueError(f"missing data node; API code={payload.get('code')}")
    keys = (period, "m240", "240m") if period == "m240" else (period,)
    key = next((k for k in keys if node.get(k)), None)
    rows = node.get(key, []) if key else []
    if not rows:
        raise ValueError(f"no native {period} candles; response keys={list(node.keys())}")
    valid = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            o, c, h, l = (float(row[i]) for i in range(1, 5))
        except (TypeError, ValueError):
            continue
        if min(o, c, h, l) <= 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"invalid OHLC row: {row[:5]}")
        valid.append(row)
    if not valid:
        raise ValueError("no valid OHLC rows")
    return {"status": "PASS", "period_key": key, "rows": len(valid),
            "first_bar": valid[0][0], "last_bar": valid[-1][0],
            "latest_close": float(valid[-1][2])}

def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    end = date.today()
    start = end - timedelta(days=180)
    report = {"provider": "Tencent Finance", "endpoint": ENDPOINT,
              "tested_at": datetime.now().isoformat(timespec="seconds"),
              "requested_period": "m240 (native 4H; no aggregation)",
              "start_date": start.isoformat(), "end_date": end.isoformat(),
              "symbols_total": len(config["symbols"]), "symbols_ok_4h": 0,
              "symbols_missing_4h": 0, "results": []}
    for code, name in config["symbols"]:
        symbol = market_symbol(code)
        item = {"code": code, "symbol": symbol, "name": name, "status": "FAIL"}
        try:
            item.update(fetch_period(symbol, "m240", start, end))
            report["symbols_ok_4h"] += 1
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            report["symbols_missing_4h"] += 1
        report["results"].append(item)
        time.sleep(0.15)
    report["status"] = ("PASS" if report["symbols_missing_4h"] == 0
                        else "PARTIAL" if report["symbols_ok_4h"] else "FAIL")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["symbols_ok_4h"] else 1

if __name__ == "__main__":
    sys.exit(main())
