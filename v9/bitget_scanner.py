"""VEGAS V9 scanner: 4H observation, 2H formal signal confirmation."""
from __future__ import annotations
import json, math, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any
from vegas_signals import detect_formal_signals

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
GRANULARITY = "2H"
OBSERVATION_GRANULARITY = "4H"
# 4H EMA676 needs a long warm-up to reduce sensitivity to its seed value.
# Fetch up to five EMA676 periods when the market has that much history.
CANDLE_LIMIT = 800
EMA_HISTORY_LIMIT = 3500
CANDLE_PAGE_LIMIT = 1000
HISTORY_CANDLE_PAGE_LIMIT = 200
TIMEOUT = 15
STATE_PATH = os.environ.get("V9_SIGNAL_STATE_PATH", "v9/.signal-state.json")
CORE_MARKETS = ("BTC", "HYPE", "XAU", "CL")
STOCKS = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC", "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK", "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX")
SYMBOLS = tuple(f"{x}USDT" for x in (*CORE_MARKETS, *STOCKS))

class BitgetError(RuntimeError):
    pass

def get_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "VEGAS-V9/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        raise BitgetError(f"Bitget request failed: {exc}") from exc
    if payload.get("code") != "00000":
        raise BitgetError(f"Bitget API error {payload.get('code')}: {payload.get('msg', 'unknown')}")
    return payload

def fetch_candles(symbol: str, granularity: str = GRANULARITY) -> list[dict[str, Any]]:
    interval_ms = {"2H": 2 * 3600000, "4H": 4 * 3600000}.get(granularity)
    if interval_ms is None:
        raise ValueError(f"Unsupported V9 candle granularity: {granularity}")

    # 2H only needs a short EMA12 warm-up; 4H Vegas bands need much deeper
    # history, especially EMA576/EMA676. Bitget pages are fetched backwards.
    # The historical-candles endpoint returns finished candles only.
    target_count = EMA_HISTORY_LIMIT if granularity == OBSERVATION_GRANULARITY else CANDLE_LIMIT
    collected: dict[int, dict[str, Any]] = {}
    end_time: int | None = None

    history_endpoint = granularity == OBSERVATION_GRANULARITY
    endpoint_path = (
        "/api/v2/mix/market/history-candles"
        if history_endpoint else "/api/v2/mix/market/candles"
    )
    page_limit = HISTORY_CANDLE_PAGE_LIMIT if history_endpoint else CANDLE_PAGE_LIMIT

    while len(collected) < target_count:
        page_size = min(page_limit, target_count - len(collected))
        params = {
            "symbol": symbol,
            "productType": PRODUCT_TYPE,
            "granularity": granularity,
            "limit": str(page_size),
        }
        if end_time is not None:
            params["endTime"] = str(end_time)
        payload = get_json(endpoint_path, params)
        rows = payload.get("data") or []
        if not rows:
            break

        page_timestamps: list[int] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts = int(row[0])
                candle = {
                    "timestamp_ms": ts,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "closed": False,
                }
            except (TypeError, ValueError, IndexError):
                continue
            if ts in collected:
                raise BitgetError(f"Duplicate candle timestamp: {ts}")
            collected[ts] = candle
            page_timestamps.append(ts)

        if not page_timestamps:
            break
        oldest_ts = min(page_timestamps)
        # Prevent an API pagination loop if the endpoint ignores endTime.
        if end_time is not None and oldest_ts >= end_time:
            break
        end_time = oldest_ts - 1
        if len(rows) < page_size:
            break

    candles = [collected[ts] for ts in sorted(collected)]
    now = int(time.time() * 1000)
    for candle in candles:
        ts = candle["timestamp_ms"]
        prices = [candle[k] for k in ("open", "high", "low", "close")]
        if not all(math.isfinite(v) and v > 0 for v in prices):
            raise BitgetError(f"Invalid OHLC value at {ts}")
        if (
            candle["high"] < max(candle["open"], candle["close"])
            or candle["low"] > min(candle["open"], candle["close"])
            or candle["low"] > candle["high"]
        ):
            raise BitgetError(f"Invalid OHLC range at {ts}")
        candle["closed"] = ts + interval_ms <= now
    return candles

def load_state() -> dict[str, dict[str, Any]]:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_state(state: dict[str, dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, STATE_PATH)

def scan_market_data() -> dict[str, Any]:
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).date()
    # A timeframe change invalidates observations and accumulated signals from the prior rule version.
    rule_version = 3
    loaded_state = load_state()
    version_record = loaded_state.get("__rule_version__", {})
    rules_changed = version_record.get("version") != rule_version
    if rules_changed:
        state: dict[str, dict[str, Any]] = {}
        daily_state = {"date": today.isoformat(), "signals": []}
    else:
        state = {key: value for key, value in loaded_state.items()
                 if key == "__daily_formal_signals__" or key == "__rule_version__" or key in SYMBOLS}
        daily_state = state.get("__daily_formal_signals__", {})
        if daily_state.get("date") != today.isoformat():
            daily_state = {"date": today.isoformat(), "signals": []}
    daily_signals = [
        signal for signal in daily_state.get("signals", [])
        if isinstance(signal, dict)
        and str(signal.get("symbol", "")).upper() in SYMBOLS
        and signal.get("formal_signal") is True
        and signal.get("observation_timeframe") == "4H"
        and signal.get("filter_line") == "2H EMA12"
        and signal.get("phase") == "信号期"
    ]
    # The 27 selected markets are the fixed V9 scan pool; do not filter by turnover.
    scan_symbols = list(SYMBOLS)

    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Bitget Mix USDT-FUTURES",
        "scan_timeframes": [OBSERVATION_GRANULARITY, GRANULARITY],
        "symbols_total": len(scan_symbols),
        "symbols_ok": 0,
        "symbols_excluded": 0,
        "scan_status": "running",
        "failed_symbols": [],
        "symbols_warmup_insufficient": 0,
        "warmup_insufficient_symbols": [],
        "results": [],
        "signals": [],
    }
    for symbol in scan_symbols:
        item = {"symbol": symbol, "timeframes": {}}
        try:
            candles_2h = fetch_candles(symbol, GRANULARITY)
            candles_4h = fetch_candles(symbol, OBSERVATION_GRANULARITY)
            closed_2h = [c for c in candles_2h if c["closed"]]
            closed_4h = [c for c in candles_4h if c["closed"]]
            if not closed_2h:
                raise BitgetError("No closed 2H candles returned")
            if not closed_4h:
                raise BitgetError("No closed 4H candles returned")
            signals = detect_formal_signals(symbol, candles_2h, candles_4h, state.setdefault(symbol, {}))
            report["signals"].extend(s for s in signals if datetime.fromtimestamp(s["candle_timestamp_ms"] / 1000, tz=tz).date() == today)
            item["timeframes"][GRANULARITY] = {"candles_received": len(candles_2h), "closed_candles": len(closed_2h), "latest_closed_candle_ms": closed_2h[-1]["timestamp_ms"], "latest_closed_price": closed_2h[-1]["close"]}
            warmup_sufficient = len(closed_4h) >= EMA_HISTORY_LIMIT
            item["timeframes"][OBSERVATION_GRANULARITY] = {
                "candles_received": len(candles_4h),
                "closed_candles": len(closed_4h),
                "latest_closed_candle_ms": closed_4h[-1]["timestamp_ms"],
                "latest_closed_price": closed_4h[-1]["close"],
                "ema676_warmup_target": EMA_HISTORY_LIMIT,
                "ema676_warmup_sufficient": warmup_sufficient,
            }
            item.update({"data_available": True, "excluded_reason": None})
            report["symbols_ok"] += 1
            if not warmup_sufficient:
                report["symbols_warmup_insufficient"] += 1
                report["warmup_insufficient_symbols"].append({
                    "symbol": symbol,
                    "candles_received": len(candles_4h),
                    "warmup_target": EMA_HISTORY_LIMIT,
                })
        except Exception as exc:
            error = str(exc)
            item["timeframes"]["error"] = {"message": error, "stage": "market_data_or_signal_processing"}
            item.update({"data_available": False, "excluded_reason": error})
            report["symbols_excluded"] += 1
            report["failed_symbols"].append({"symbol": symbol, "error": error})
        report["results"].append(item)
    daily_by_key = {
        (str(s.get("symbol")), int(s.get("candle_timestamp_ms", 0)), str(s.get("filter_side"))): s
        for s in daily_signals if isinstance(s, dict)
    }
    for signal in report["signals"]:
        daily_by_key[(str(signal.get("symbol")), int(signal.get("candle_timestamp_ms", 0)), str(signal.get("filter_side")))] = signal
    daily_state = {"date": today.isoformat(), "signals": list(daily_by_key.values())}
    state["__daily_formal_signals__"] = daily_state
    state["__rule_version__"] = {"version": rule_version}
    report["signals"] = daily_state["signals"]
    all_symbols_scanned = (
        report["symbols_ok"] == report["symbols_total"]
        and report["symbols_excluded"] == 0
    )
    report["scan_status"] = (
        "complete" if all_symbols_scanned and report["symbols_warmup_insufficient"] == 0
        else "complete_with_warmup_warning" if all_symbols_scanned
        else "partial" if report["symbols_ok"] > 0 else "failed"
    )
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return report

def scan_exit_code(report: dict[str, Any]) -> int:
    """Require all symbols to scan; distinguish warmup warnings from data failures."""
    return 0 if (
        report.get("scan_status") in {"complete", "complete_with_warmup_warning"}
        and report.get("symbols_ok") == report.get("symbols_total")
        and report.get("symbols_excluded") == 0
    ) else 1

def main() -> int:
    report = scan_market_data()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    path = os.environ.get("V9_REPORT_PATH", "v9/scan-report.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(rendered + "\n")
    return scan_exit_code(report)

if __name__ == "__main__":
    sys.exit(main())
