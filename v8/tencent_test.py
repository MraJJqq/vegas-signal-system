"""Connectivity and OHLC validation test for Tencent Finance A-share daily K-lines."""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

SYMBOLS = {
    "sh600519": "贵州茅台",
    "sz300750": "宁德时代",
    "sz000333": "美的集团",
}
ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
LOOKBACK_DAYS = 180


def fetch(symbol: str, start: date, end: date) -> dict:
    params = {
        "param": f"{symbol},day,{start.isoformat()},{end.isoformat()},200,qfq",
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; VEGAS-V8-Ashare-Test/1.0)",
            "Referer": "https://finance.qq.com/",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8", errors="replace")
    # Tencent may return JSON or JavaScript assignment: var xxx=JSON;
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError(f"response is not JSON/JSONP (HTTP body length={len(raw)})")
    payload = json.loads(match.group(0))
    if payload.get("code") not in (None, 0, "0"):
        raise ValueError(f"Tencent API returned code={payload.get('code')}")
    node = (payload.get("data") or {}).get(symbol)
    if not isinstance(node, dict):
        raise ValueError(f"missing data node for {symbol}")
    rows = node.get("day") or node.get("qfqday") or node.get("hfqday") or []
    if not rows:
        raise ValueError(f"zero daily K-lines; keys={list(node.keys())}")
    parsed = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            continue
        dt = str(row[0])
        o, c, h, l = (float(row[i]) for i in range(1, 5))
        if min(o, c, h, l) <= 0:
            raise ValueError(f"non-positive OHLC row: {row[:5]}")
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"OHLC consistency failure: {row[:5]}")
        parsed.append({"date": dt, "open": o, "close": c, "high": h, "low": l})
    if not parsed:
        raise ValueError("no valid OHLC rows after parsing")
    return {
        "status": "PASS",
        "rows": len(parsed),
        "first_date": parsed[0]["date"],
        "last_date": parsed[-1]["date"],
        "latest_close": parsed[-1]["close"],
        "data_key": next(k for k in ("day", "qfqday", "hfqday") if node.get(k)),
    }


def main() -> int:
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    report = {
        "provider": "Tencent Finance",
        "endpoint": ENDPOINT,
        "tested_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "period": "daily",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "symbols_total": len(SYMBOLS),
        "results": [],
    }
    for symbol, name in SYMBOLS.items():
        item = {"symbol": symbol, "name": name, "status": "FAIL"}
        try:
            item.update(fetch(symbol, start, end))
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        report["results"].append(item)
    report["symbols_ok"] = sum(x["status"] == "PASS" for x in report["results"])
    report["symbols_failed"] = report["symbols_total"] - report["symbols_ok"]
    report["status"] = "PASS" if report["symbols_failed"] == 0 else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
