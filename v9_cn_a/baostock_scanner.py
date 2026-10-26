"""Baostock native-1H A-share scanner; isolated from the US V9 system."""
from __future__ import annotations
import json, os, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import baostock as bs
from vegas_signals_cn import detect_formal_signals

TZ = timezone(timedelta(hours=8))
STATE_PATH = Path(os.environ.get("V9_CN_A_STATE_PATH", "v9_cn_a/.signal-state.json"))
REPORT_PATH = Path(os.environ.get("V9_CN_A_REPORT_PATH", "v9_cn_a/scan-report.json"))
POOL_PATH = Path(os.environ.get("V9_CN_A_POOL_PATH", "v9_cn_a/baostock-stock-pool.json"))
CACHE_PATH = Path(os.environ.get("V9_CN_A_CANDLE_CACHE_PATH", "v9_cn_a/.candle-cache.json"))
MAX_CANDLES, REFRESH_DAYS, INITIAL_HISTORY_DAYS = 1800, 10, 1460

def load_json(path: Path, default: Any) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default

def load_pool() -> list[dict[str, str]]:
    stocks = load_json(POOL_PATH, {}).get("stocks", [])
    if len(stocks) != 2000: raise RuntimeError(f"Expected 2000 stocks; got {len(stocks)}")
    codes = [x.get("code") for x in stocks]
    if any(not c for c in codes) or len(set(codes)) != len(codes): raise RuntimeError("Pool has missing or duplicate codes")
    return stocks

def fetch_hourly(code: str, cached: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if cached:
        latest = max(int(x["timestamp_ms"]) for x in cached)
        start = (datetime.fromtimestamp(latest / 1000, tz=TZ).date() - timedelta(days=REFRESH_DAYS)).isoformat()
    else:
        start = (datetime.now(TZ).date() - timedelta(days=INITIAL_HISTORY_DAYS)).isoformat()
    end = datetime.now(TZ).date().isoformat()
    rs = bs.query_history_k_data_plus(code, "date,time,code,open,high,low,close,volume,amount",
        start_date=start, end_date=end, frequency="60", adjustflag="3")
    if rs.error_code != "0": raise RuntimeError(f"Baostock {rs.error_code}: {rs.error_msg}")
    rows, now_ms = [], int(time.time() * 1000)
    while rs.next():
        row = dict(zip(rs.fields, rs.get_row_data()))
        try:
            digits = "".join(ch for ch in row["time"] if ch.isdigit())
            stamp = datetime.strptime(digits[:14], "%Y%m%d%H%M%S").replace(tzinfo=TZ)
            opened, high, low, close = (float(row[k]) for k in ("open", "high", "low", "close"))
            if min(opened, high, low, close) <= 0 or low > min(opened, close) or high < max(opened, close): continue
            ts = int(stamp.timestamp() * 1000)
            rows.append({"timestamp_ms": ts, "open": opened, "high": high, "low": low, "close": close,
                         "volume": float(row.get("volume") or 0), "closed": ts + 3600000 <= now_ms})
        except (ValueError, KeyError, TypeError, OverflowError): continue
    merged = {int(x["timestamp_ms"]): x for x in cached}
    merged.update({int(x["timestamp_ms"]): x for x in rows})
    result = sorted(merged.values(), key=lambda x: int(x["timestamp_ms"]))[-MAX_CANDLES:]
    if not result: raise ValueError("Baostock returned no valid 1H OHLC candles")
    return result

def send_bark(signals: list[dict[str, Any]]) -> dict[str, Any]:
    key = os.environ.get("BARK_KEY", "").strip()
    if not key: return {"status": "skipped", "reason": "BARK_KEY_missing"}
    symbols, seen = [], set()
    for signal in signals:
        symbol = str(signal.get("symbol", "")).strip().upper()
        if symbol and symbol not in seen: symbols.append(symbol); seen.add(symbol)
    body = "A股\n" + ("\n".join("   ".join(f"▰ {s} ▰" for s in symbols[i:i+3]) for i in range(0, len(symbols), 3)) if symbols else "▰ No change ▰")
    payload = json.dumps({"device_key": key, "title": "VEGAS V9 A股 1H", "body": body,
                          "group": "VEGAS V9 A股", "level": "active"}, ensure_ascii=False).encode()
    req = urllib.request.Request("https://api.day.app/push", data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8", "replace")
            if not 200 <= response.status < 300: raise RuntimeError(f"Bark HTTP {response.status}: {text[:200]}")
        try: parsed = json.loads(text)
        except json.JSONDecodeError: parsed = {}
        if isinstance(parsed, dict) and parsed.get("code") not in (None, 200): raise RuntimeError(f"Bark rejected push: {text[:200]}")
        return {"status": "sent", "signals": len(signals), "symbols": symbols}
    except Exception as exc: return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

def main() -> int:
    today = datetime.now(TZ).date().isoformat()
    pool, state, cache = load_pool(), load_json(STATE_PATH, {}), load_json(CACHE_PATH, {})
    daily = state.get("__daily_formal_signals__", {})
    if daily.get("date") != today: daily = {"date": today, "signals": []}
    bykey = {(s.get("symbol"), s.get("candle_timestamp_ms"), s.get("filter_side")): s
             for s in daily.get("signals", []) if isinstance(s, dict)}
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "source": "Baostock native 60-minute candles",
        "timeframe": "1H", "minimum_closed_candles": 676, "pool_size": len(pool),
        "symbols_ok": 0, "symbols_excluded": [], "results": [], "new_signals": [], "signals": []}
    login = bs.login()
    if login.error_code != "0": raise RuntimeError(f"Baostock login failed: {login.error_code} {login.error_msg}")
    try:
        for index, item in enumerate(pool, 1):
            code, name = item["code"], item["name"]
            try:
                candles = fetch_hourly(code, cache.get(code, [])); cache[code] = candles
                closed_count = sum(bool(c.get("closed")) for c in candles)
                if closed_count < 676: raise ValueError(f"Not enough closed native 1H candles for EMA676: {closed_count}")
                symbol = code.upper()
                signals = detect_formal_signals(symbol, candles, state.setdefault(symbol, {}))
                for signal in signals:
                    signal["name"] = name
                    if datetime.fromtimestamp(signal["candle_timestamp_ms"] / 1000, tz=TZ).date().isoformat() == today:
                        bykey[(signal["symbol"], signal["candle_timestamp_ms"], signal["filter_side"])] = signal
                        report["new_signals"].append(signal)
                report["symbols_ok"] += 1
                report["results"].append({"code": code, "name": name, "data_available": True,
                    "candles_1h_total": len(candles), "candles_1h_closed": closed_count,
                    "latest_closed_candle_ms": max((int(c["timestamp_ms"]) for c in candles if c.get("closed")), default=None)})
            except Exception as exc:
                report["symbols_excluded"].append({"code": code, "name": name, "reason": str(exc)})
                report["results"].append({"code": code, "name": name, "data_available": False, "error": str(exc)})
            if index % 100 == 0: print(f"[{index}/{len(pool)}] valid={report['symbols_ok']} excluded={len(report['symbols_excluded'])}")
    finally: bs.logout()
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"); tmp.replace(CACHE_PATH)
    report["signals"] = list(bykey.values())
    state["__daily_formal_signals__"] = {"date": today, "signals": report["signals"]}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"); tmp.replace(STATE_PATH)
    report["bark_notification"] = send_bark(report["signals"])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2))
    return 0 if report["symbols_ok"] >= 1600 else 1

if __name__ == "__main__": raise SystemExit(main())
