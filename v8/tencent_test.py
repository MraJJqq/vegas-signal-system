"""Test Tencent Finance daily K-lines for the configured A-share candidate pool.

This is a data-source validation step, not the formal VEGAS scanner. It deliberately
does not treat daily candles as 4H candles.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

CONFIG = Path(__file__).with_name("ashare_universe.json")
ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
LOOKBACK_DAYS = 180
TIMEOUT_SECONDS = 15


def market_symbol(code: str) -> str:
    return ("sh" if code.startswith(("5", "6", "9")) else "sz") + code


def fetch_daily(symbol: str, start: date, end: date) -> dict:
    params = {"param": f"{symbol},day,{start.isoformat()},{end.isoformat()},200,qfq"}
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; VEGAS-V8-Ashare-Test/1.0)",
            "Referer": "https://finance.qq.com/",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8", errors="replace")
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError(f"response is not JSON/JSONP (body length={len(raw)})")
    payload = json.loads(match.group(0))
    node = (payload.get("data") or {}).get(symbol)
    if not isinstance(node, dict):
        raise ValueError(f"missing data node; API code={payload.get('code')}")
    key = next((k for k in ("day", "qfqday", "hfqday") if node.get(k)), None)
    rows = node.get(key, []) if key else []
    if not rows:
        raise ValueError(f"zero daily K-lines; keys={list(node.keys())}")
    valid = 0
    for row in rows:
        if not isinstance(row, list) or len(row) < 5:
            continue
        o, c, h, l = (float(row[i]) for i in range(1, 5))
        if min(o, c, h, l) <= 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"invalid OHLC row: {row[:5]}")
        valid += 1
    if not valid:
        raise ValueError("no valid OHLC rows")
    return {"status": "PASS", "rows": valid, "first_date": rows[0][0],
            "last_date": rows[-1][0], "latest_close": float(rows[-1][2])}


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    report = {
        "provider": "Tencent Finance",
        "endpoint": ENDPOINT,
        "tested_at": datetime.now().isoformat(timespec="seconds"),
        "period": "daily",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "symbols_total": len(config["symbols"]),
        "symbols_ok": 0,
        "symbols_failed": 0,
        "results": [],
        "note": "Daily K-lines validate source connectivity only; they are not used as 4H Vegas candles.",
    }
    for code, name in config["symbols"]:
        symbol = market_symbol(code)
        item = {"code": code, "symbol": symbol, "name": name, "status": "FAIL"}
        try:
            item.update(fetch_daily(symbol, start, end))
            report["symbols_ok"] += 1
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            report["symbols_failed"] += 1
        report["results"].append(item)
    report["status"] = "PASS" if report["symbols_failed"] == 0 else "PARTIAL" if report["symbols_ok"] else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["symbols_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
