"""Build a data-qualified V8 A-share pool using Tencent native 4H candles.

The stock-code catalogue is a replaceable public reference list; all market candles
are fetched from Tencent. This builds a *scan-capable* pool, not a list of stocks
that happen to signal today. Incomplete/invalid candles or insufficient EMA history
exclude a stock.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
# Public A-share reference catalogue; all OHLC data remains Tencent sourced.
UNIVERSE_URL = "https://raw.githubusercontent.com/guidebee/china-stock-data/main/data/company/companies.json"
TIMEOUT = 15
MIN_CLOSED_CANDLES = 700  # Covers EMA676 warm-up plus recent closed bars.
CHUNK_DAYS = 180
REQUEST_PAUSE = 0.12
USER_AGENT = "Mozilla/5.0 (compatible; VEGAS-V8-Ashare-Pool/1.0)"


def request_text(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": "https://finance.qq.com/",
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_jsonp(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError("response is not JSON/JSONP")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("unexpected JSON root")
    return value


def normalize_catalog(payload: Any) -> list[tuple[str, str]]:
    """Normalize common A-share catalogue shapes without assuming one API schema."""
    found: dict[str, str] = {}
    code_keys = ("code", "symbol", "stock_code", "stockCode", "ts_code",
                 "tsCode", "dm", "api_code", "security_code", "ticker")
    name_keys = ("name", "stock_name", "stockName", "mc", "security_name",
                 "short_name", "简称", "名称")
    valid_prefixes = (
        "000", "001", "002", "003", "300", "301", "600", "601", "603",
        "605", "688", "689", "430", "831", "832", "833", "834", "835",
        "836", "837", "838", "839", "870", "871", "872", "873", "920"
    )

    def add(code_value: Any, name_value: Any) -> bool:
        if code_value is None or name_value is None:
            return False
        raw_code = str(code_value).strip().upper()
        # Accept 000001, 000001.SZ, SZ000001, and sh/sz/bj-prefixed symbols.
        match = re.search(r"(?<!\d)(\d{6})(?:\.(?:SH|SZ|BJ))?$", raw_code)
        if not match:
            match = re.fullmatch(r"(?:SH|SZ|BJ)(\d{6})", raw_code)
        if not match:
            return False
        code = match.group(1)
        name = str(name_value).strip()
        if not name or not code.startswith(valid_prefixes):
            return False
        # Reject placeholder names and accidental code-as-name rows.
        if name == code or name.lower() in {"none", "null", "nan"}:
            return False
        # Reject catalogue corruption such as code=920000, name=bj920001.
        if re.fullmatch(r"(?i)(?:SH|SZ|BJ)?\d{6}(?:\.(?:SH|SZ|BJ))?", name):
            return False
        found[code] = name
        return True

    def walk(node: Any, key_hint: str = "") -> None:
        if isinstance(node, dict) and "stock_type" in node:
            # The catalogue includes B-shares too; retain only listed A-share segments.
            if str(node.get("stock_type", "")).strip().lower() not in {"sh_a", "sz_a", "kcb", "hs_bjs"}:
                return
        if isinstance(node, list):
            # Common catalogue format: [code, name].
            if len(node) >= 2 and not isinstance(node[0], (dict, list)) and not isinstance(node[1], (dict, list)):
                if add(node[0], node[1]):
                    return
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        code_value = next((node[k] for k in code_keys if k in node and node[k] not in (None, "")), None)
        name_value = next((node[k] for k in name_keys if k in node and node[k] not in (None, "")), None)
        if code_value is not None and name_value is not None and add(code_value, name_value):
            return

        # Some APIs return { "000001": "平安银行", ... } or exchange-prefixed keys.
        if re.fullmatch(r"(?:(?:SH|SZ|BJ)?\d{6})(?:\.(?:SH|SZ|BJ))?", key_hint.upper()):
            if isinstance(node, (str, int, float)) and add(key_hint, node):
                return
        for key, value in node.items():
            if isinstance(key, str) and re.fullmatch(r"(?:(?:SH|SZ|BJ)?\d{6})(?:\.(?:SH|SZ|BJ))?", key.upper()):
                if isinstance(value, str):
                    if add(key, value):
                        continue
                elif isinstance(value, dict):
                    inner_name = next((value[k] for k in name_keys if k in value and value[k] not in (None, "")), None)
                    if inner_name is not None and add(key, inner_name):
                        continue
            # Recurse into nested envelopes such as data/result/stocks/list and exchange groups.
            if isinstance(value, (dict, list)):
                walk(value, str(key))

    walk(payload)
    if not found:
        if isinstance(payload, dict):
            shape = f"dict keys={list(payload.keys())[:20]}"
            for key in ("data", "stocks", "list", "result"):
                value = payload.get(key)
                if isinstance(value, dict):
                    shape += f"; {key} keys={list(value.keys())[:10]}"
                elif isinstance(value, list) and value:
                    shape += f"; {key} first_item_type={type(value[0]).__name__}"
        elif isinstance(payload, list):
            shape = f"list length={len(payload)}; first_item_type={type(payload[0]).__name__ if payload else 'empty'}"
        else:
            shape = f"root_type={type(payload).__name__}"
        raise ValueError(f"catalogue parsed but no A-share symbols were recognized ({shape})")
    return sorted(found.items())

def market_symbol(code: str) -> str:
    if code.startswith(("6", "5", "9")):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


def fetch_chunk(symbol: str, start: date, end: date) -> list[list[Any]]:
    params = {"param": f"{symbol},m240,{start.isoformat()},{end.isoformat()},200,qfq"}
    payload = parse_jsonp(request_text(f"{ENDPOINT}?{urllib.parse.urlencode(params)}"))
    node = (payload.get("data") or {}).get(symbol)
    if not isinstance(node, dict):
        raise ValueError("missing Tencent data node")
    rows = node.get("m240") or node.get("240m") or []
    if not isinstance(rows, list):
        raise ValueError("Tencent 4H rows are malformed")
    return rows


def fetch_history(symbol: str, end: date) -> list[dict[str, Any]]:
    # Request overlapping 180-day windows, then de-duplicate timestamps.
    start = end - timedelta(days=5 * 365)
    rows_by_time: dict[str, dict[str, Any]] = {}
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end)
        rows = fetch_chunk(symbol, cursor, chunk_end)
        for row in rows:
            if not isinstance(row, list) or len(row) < 5:
                continue
            stamp = str(row[0])
            try:
                o, c, h, l = (float(row[i]) for i in range(1, 5))
            except (TypeError, ValueError):
                continue
            if min(o, c, h, l) <= 0 or h < max(o, c, l) or l > min(o, c, h):
                raise ValueError(f"invalid OHLC candle {row[:5]}")
            # Tencent timestamps are generally YYYY-MM-DD HH:mm; retain only valid dates.
            try:
                bar_date = datetime.fromisoformat(stamp.replace("T", " ").split("+")[0]).date()
            except ValueError:
                try:
                    bar_date = date.fromisoformat(stamp[:10])
                except ValueError:
                    raise ValueError(f"unrecognized candle timestamp: {stamp}")
            if bar_date <= end:
                rows_by_time[stamp] = {
                    "timestamp": stamp, "date": bar_date.isoformat(),
                    "open": o, "high": h, "low": l, "close": c,
                }
        cursor = chunk_end
        time.sleep(REQUEST_PAUSE)
    return sorted(rows_by_time.values(), key=lambda x: x["timestamp"])


def main() -> int:
    tested_at = datetime.now().astimezone().isoformat(timespec="seconds")
    catalog = normalize_catalog(json.loads(request_text(UNIVERSE_URL)))
    end = date.today()
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    total = len(catalog)
    print(f"Loaded {total} A-share candidates; validating Tencent native 4H data...", flush=True)

    for index, (code, name) in enumerate(catalog, 1):
        symbol = market_symbol(code)
        try:
            candles = fetch_history(symbol, end)
            if len(candles) < MIN_CLOSED_CANDLES:
                raise ValueError(f"insufficient native 4H history: {len(candles)} < {MIN_CLOSED_CANDLES}")
            # Ensure candles are recent enough; stale symbols are excluded.
            latest_date = date.fromisoformat(candles[-1]["date"])
            if (end - latest_date).days > 14:
                raise ValueError(f"stale latest 4H candle: {latest_date.isoformat()}")
            eligible.append({
                "code": code, "name": name, "symbol": symbol,
                "candles_available": len(candles),
                "first_candle": candles[0]["timestamp"],
                "latest_candle": candles[-1]["timestamp"],
                "status": "DATA_OK",
            })
        except Exception as exc:
            excluded.append({"code": code, "name": name, "reason": f"{type(exc).__name__}: {exc}"})
        if index % 100 == 0 or index == total:
            print(f"Progress: {index}/{total}; data-qualified={len(eligible)}; excluded={len(excluded)}", flush=True)

    output = {
        "name": "V8 A-share data-qualified scan pool",
        "market": "CN A-shares",
        "provider": "Tencent Finance native m240 candles",
        "catalogue_source": UNIVERSE_URL,
        "tested_at": tested_at,
        "requested_timeframe": "native 4H (m240); no daily/hourly aggregation",
        "minimum_native_4h_candles": MIN_CLOSED_CANDLES,
        "status": "READY_FOR_VEGAS_SCAN" if eligible else "NO_ELIGIBLE_SYMBOLS",
        "candidate_count": total,
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "symbols": [[x["code"], x["name"]] for x in eligible],
        "validation_details": eligible,
        "excluded": excluded,
        "note": "Pool eligibility means valid sufficient data for the unchanged V8 rules; it does not mean a formal Vegas signal exists right now.",
    }
    pool_path = ROOT / "ashare_scan_pool.json"
    report_path = ROOT / "ashare_pool_build_report.json"
    pool_path.write_text(json.dumps({k: v for k, v in output.items() if k not in ("validation_details", "excluded")}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": output["status"], "candidate_count": total,
        "eligible_count": len(eligible), "excluded_count": len(excluded),
        "pool_file": str(pool_path), "report_file": str(report_path),
    }, ensure_ascii=False, indent=2))
    return 0 if eligible else 1


if __name__ == "__main__":
    sys.exit(main())
