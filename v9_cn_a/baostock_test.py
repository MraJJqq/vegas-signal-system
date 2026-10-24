"""Independent Baostock 1H data-quality test for 50 A-share candidates.
This script does not import or modify the production Tencent scanner or signal engine.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import baostock as bs

TZ = ZoneInfo("Asia/Shanghai")
OUT = Path(os.environ.get("BAOSTOCK_TEST_REPORT", "v9_cn_a/baostock-test-report.json"))

# 50 diversified, relatively liquid A-share candidates across finance, consumer,
# industrials, energy, healthcare, technology and broad-market leaders.
STOCKS = [
    ("sh.600036", "招商银行"), ("sh.600519", "贵州茅台"),
    ("sh.601318", "中国平安"), ("sh.600030", "中信证券"),
    ("sh.601166", "兴业银行"), ("sh.600900", "长江电力"),
    ("sh.600276", "恒瑞医药"), ("sh.601888", "中国中免"),
    ("sh.600887", "伊利股份"), ("sh.600809", "山西汾酒"),
    ("sh.601012", "隆基绿能"), ("sh.600438", "通威股份"),
    ("sh.601668", "中国建筑"), ("sh.601398", "工商银行"),
    ("sh.601288", "农业银行"), ("sh.601857", "中国石油"),
    ("sh.600028", "中国石化"), ("sh.600104", "上汽集团"),
    ("sh.601766", "中国中车"), ("sh.600050", "中国联通"),
    ("sz.000001", "平安银行"), ("sz.000333", "美的集团"),
    ("sz.000651", "格力电器"), ("sz.000858", "五粮液"),
    ("sz.002415", "海康威视"), ("sz.002594", "比亚迪"),
    ("sz.000725", "京东方A"), ("sz.002475", "立讯精密"),
    ("sz.300750", "宁德时代"), ("sz.300059", "东方财富"),
    ("sz.300124", "汇川技术"), ("sz.300760", "迈瑞医疗"),
    ("sz.300015", "爱尔眼科"), ("sz.300274", "阳光电源"),
    ("sz.002230", "科大讯飞"), ("sz.002371", "北方华创"),
    ("sh.688981", "中芯国际"), ("sh.688041", "海光信息"),
    ("sh.688111", "金山办公"), ("sh.688012", "中微公司"),
    ("sh.601899", "紫金矿业"), ("sh.603259", "药明康德"),
    ("sh.600309", "万华化学"), ("sh.601225", "陕西煤业"),
    ("sh.601088", "中国神华"), ("sz.000063", "中兴通讯"),
    ("sz.002142", "宁波银行"), ("sz.002352", "顺丰控股"),
    ("sz.300033", "同花顺"), ("sz.003816", "中国广核"),
]


def parse_dt(value: str) -> datetime:
    # Baostock's 60-minute records normally expose date as YYYY-MM-DD HH:MM:SS.
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)


def main() -> int:
    now = datetime.now(TZ)
    start = (now.date() - timedelta(days=45)).isoformat()
    end = now.date().isoformat()
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"Baostock login failed: {login.error_code} {login.error_msg}")

    results = []
    try:
        for code, name in STOCKS:
            item = {
                "code": code, "name": name, "status": "error",
                "error": None, "record_count": 0, "latest_record": None,
                "latest_closed_candle": None, "ohlc_valid": False,
            }
            try:
                rs = bs.query_history_k_data_plus(
                    code,
                    "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus,pctChg",
                    start_date=start,
                    end_date=end,
                    frequency="60",
                    adjustflag="3",
                )
                if rs.error_code != "0":
                    raise RuntimeError(f"{rs.error_code}: {rs.error_msg}")

                rows = []
                while rs.next():
                    row = dict(zip(rs.fields, rs.get_row_data()))
                    try:
                        stamp = parse_dt(row["date"])
                        o, h, low, close = (float(row[k]) for k in ("open", "high", "low", "close"))
                        valid = all(v > 0 for v in (o, h, low, close)) and low <= min(o, close) <= max(o, close) <= h
                        row["_timestamp"] = stamp
                        row["_ohlc_valid"] = valid
                        rows.append(row)
                    except (ValueError, KeyError) as exc:
                        item["error"] = f"invalid row: {exc}"

                item["record_count"] = len(rows)
                if rows:
                    rows.sort(key=lambda r: r["_timestamp"])
                    latest = rows[-1]
                    closed = [r for r in rows if r["_timestamp"] + timedelta(hours=1) <= now]
                    item["latest_record"] = {
                        "timestamp": latest["date"],
                        "open": latest["open"], "high": latest["high"],
                        "low": latest["low"], "close": latest["close"],
                        "volume": latest["volume"], "ohlc_valid": latest["_ohlc_valid"],
                    }
                    if closed:
                        c = closed[-1]
                        item["latest_closed_candle"] = {
                            "timestamp": c["date"],
                            "open": c["open"], "high": c["high"],
                            "low": c["low"], "close": c["close"],
                            "volume": c["volume"], "ohlc_valid": c["_ohlc_valid"],
                        }
                    item["ohlc_valid"] = all(r["_ohlc_valid"] for r in rows[-10:])
                    item["status"] = "ok" if item["record_count"] and item["latest_closed_candle"] else "incomplete"
                else:
                    item["status"] = "no_data"
                    item["error"] = item["error"] or "No 60-minute rows returned"
            except Exception as exc:
                item["error"] = str(exc)
            results.append(item)
            print(f"[{len(results):02d}/50] {code} {name}: {item['status']} "
                  f"rows={item['record_count']} latest_closed="
                  f"{(item['latest_closed_candle'] or {}).get('timestamp')}")
            time.sleep(0.15)
    finally:
        bs.logout()

    summary = {
        "provider": "Baostock",
        "frequency": "60-minute",
        "timezone": "Asia/Shanghai",
        "tested_at": now.isoformat(),
        "query_range": {"start": start, "end": end},
        "stock_count": len(STOCKS),
        "ok_count": sum(x["status"] == "ok" for x in results),
        "incomplete_count": sum(x["status"] == "incomplete" for x in results),
        "no_data_count": sum(x["status"] == "no_data" for x in results),
        "error_count": sum(x["status"] == "error" for x in results),
        "valid_recent_ohlc_count": sum(x["ohlc_valid"] for x in results),
        "stocks": results,
        "notes": [
            "This is a data-source test only; it does not generate trading signals.",
            "A candle is provisionally classified closed when its timestamp plus 60 minutes is no later than the test time; verify timestamp semantics against the provider before production use.",
            "Not investment advice."
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "stocks"}, ensure_ascii=False, indent=2))
    print(f"Report written to {OUT}")
    return 0 if summary["ok_count"] >= 40 else 1


if __name__ == "__main__":
    raise SystemExit(main())
