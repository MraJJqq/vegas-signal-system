"""Standalone connectivity test for AKShare A-share daily history. Does not alter V8 signal logic."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

try:
    import akshare as ak
except Exception as exc:
    print(json.dumps({"status": "FAIL", "stage": "import", "error": str(exc)}, ensure_ascii=False, indent=2))
    raise SystemExit(1)

SYMBOLS = {
    "600519": "贵州茅台",
    "300750": "宁德时代",
    "000333": "美的集团",
}
REQUIRED_COLUMNS = {"日期", "开盘", "收盘", "最高", "最低"}
end_date = datetime.now().date()
start_date = end_date - timedelta(days=180)
report = {
    "provider": "AKShare",
    "interface": "stock_zh_a_hist",
    "tested_at": datetime.now().isoformat(timespec="seconds"),
    "period": "daily",
    "start_date": start_date.strftime("%Y%m%d"),
    "end_date": end_date.strftime("%Y%m%d"),
    "symbols_total": len(SYMBOLS),
    "symbols_ok": 0,
    "symbols_failed": 0,
    "results": [],
}

for symbol, name in SYMBOLS.items():
    item = {"symbol": symbol, "name": name, "status": "FAIL"}
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=report["start_date"],
            end_date=report["end_date"],
            adjust="",
        )
        missing = sorted(REQUIRED_COLUMNS - set(df.columns))
        if missing:
            raise ValueError(f"missing columns: {missing}")
        if df.empty:
            raise ValueError("returned zero rows")
        for col in ("开盘", "收盘", "最高", "最低"):
            df[col] = __import__("pandas").to_numeric(df[col], errors="coerce")
        if df[["开盘", "收盘", "最高", "最低"]].isna().any().any():
            raise ValueError("OHLC contains missing/non-numeric values")
        if (df["最高"] < df["最低"]).any():
            raise ValueError("high lower than low")
        if ((df["最高"] < df["开盘"]) | (df["最高"] < df["收盘"]) |
                (df["最低"] > df["开盘"]) | (df["最低"] > df["收盘"])).any():
            raise ValueError("OHLC range consistency check failed")
        item.update({
            "status": "PASS",
            "rows": int(len(df)),
            "first_date": str(df["日期"].iloc[0]),
            "last_date": str(df["日期"].iloc[-1]),
            "latest_close": float(df["收盘"].iloc[-1]),
            "columns": list(df.columns),
        })
        report["symbols_ok"] += 1
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
        report["symbols_failed"] += 1
    report["results"].append(item)

report["status"] = "PASS" if report["symbols_failed"] == 0 else "FAIL"
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report["status"] == "PASS" else 1)
