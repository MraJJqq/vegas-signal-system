"""VEGAS V9 Bitget 1H scanner."""
from __future__ import annotations
import json, math, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any
from vegas_signals import detect_formal_signals

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
GRANULARITY = "1H"
CANDLE_LIMIT = 800
TIMEOUT = 15
MIN_STOCK_TURNOVER_24H_USDT = 1_000_000
STATE_PATH = os.environ.get("V9_SIGNAL_STATE_PATH", "v9/.signal-state.json")
CORE_MARKETS = ("BTC", "HYPE", "XAU", "CL", "SNDK")
STOCKS = ("AAPL", "AMZN", "GOOGL", "NVDA", "JPM", "COIN", "CRWD", "BABA", "NFLX", "UBER", "CAT", "CEG", "CVX", "TSLA")
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

def fetch_stock_turnovers() -> tuple[dict[str, float], str | None]:
    """Return 24h USDT turnover for listed USDT futures tickers."""
    try:
        payload = get_json("/api/v2/mix/market/tickers", {"productType": PRODUCT_TYPE})
        turnovers: dict[str, float] = {}
        for ticker in payload.get("data") or []:
            symbol = str(ticker.get("symbol", ""))
            if symbol not in {f"{stock}USDT" for stock in STOCKS}:
                continue
            raw = ticker.get("quoteVolume")
            if raw is None:
                raw = ticker.get("usdtVolume")
            if raw is None:
                raw = ticker.get("turnover24h")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value >= 0:
                turnovers[symbol] = value
        return turnovers, None
    except Exception as exc:
        return {}, str(exc)

def fetch_candles(symbol: str) -> list[dict[str, Any]]:
    payload = get_json("/api/v2/mix/market/candles", {"symbol": symbol, "productType": PRODUCT_TYPE, "granularity": GRANULARITY, "limit": str(CANDLE_LIMIT)})
    candles = []
    for row in payload.get("data") or []:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            candles.append({"timestamp_ms": int(row[0]), "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]), "closed": False})
        except (TypeError, ValueError, IndexError):
            continue
    candles.sort(key=lambda x: x["timestamp_ms"])
    seen = set()
    now = int(time.time() * 1000)
    interval = 3600000
    for c in candles:
        ts = c["timestamp_ms"]
        if ts in seen:
            raise BitgetError(f"Duplicate candle timestamp: {ts}")
        seen.add(ts)
        prices = [c[k] for k in ("open", "high", "low", "close")]
        if not all(math.isfinite(v) and v > 0 for v in prices):
            raise BitgetError(f"Invalid OHLC value at {ts}")
        if c["high"] < max(c["open"], c["close"]) or c["low"] > min(c["open"], c["close"]) or c["low"] > c["high"]:
            raise BitgetError(f"Invalid OHLC range at {ts}")
        c["closed"] = ts + interval <= now
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
    # Keep only state for the approved current 19-symbol pool; discard legacy symbols.
    loaded_state = load_state()
    state = {key: value for key, value in loaded_state.items()
             if key == "__daily_formal_signals__" or key in SYMBOLS}
    daily_state = state.get("__daily_formal_signals__", {})
    if daily_state.get("date") != today.isoformat():
        daily_state = {"date": today.isoformat(), "signals": []}
    # Old same-day signals from retired pools must never be carried into notifications.
    daily_signals = [
        signal for signal in daily_state.get("signals", [])
        if isinstance(signal, dict) and str(signal.get("symbol", "")).upper() in SYMBOLS
    ]
    turnovers, turnover_error = fetch_stock_turnovers()
    scan_symbols = list(f"{x}USDT" for x in CORE_MARKETS)
    excluded_by_turnover: list[dict[str, Any]] = []
    if turnover_error:
        excluded_by_turnover = [{"symbol": f"{stock}USDT", "reason": f"Unable to verify 24h turnover; excluded safely: {turnover_error}"} for stock in STOCKS]
    else:
        for stock in STOCKS:
            symbol = f"{stock}USDT"
            turnover = turnovers.get(symbol)
            if turnover is None:
                excluded_by_turnover.append({"symbol": symbol, "turnover24h_usdt": None, "reason": "No valid Bitget USDT-FUTURES ticker"})
            elif turnover < MIN_STOCK_TURNOVER_24H_USDT:
                excluded_by_turnover.append({"symbol": symbol, "turnover24h_usdt": turnover, "reason": f"24h turnover below {MIN_STOCK_TURNOVER_24H_USDT} USDT"})
            else:
                scan_symbols.append(symbol)

    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Bitget Mix USDT-FUTURES",
        "scan_timeframes": [GRANULARITY],
        "stock_min_turnover24h_usdt": MIN_STOCK_TURNOVER_24H_USDT,
        "stock_turnover_api_error": turnover_error,
        "symbols_total": len(scan_symbols),
        "symbols_ok": 0,
        "symbols_excluded": len(excluded_by_turnover),
        "stock_symbols_excluded_by_turnover": excluded_by_turnover,
        "results": [],
        "signals": [],
    }
    for symbol in scan_symbols:
        item = {"symbol": symbol, "timeframes": {}}
        try:
            candles = fetch_candles(symbol)
            closed = [c for c in candles if c["closed"]]
            if not closed:
                raise BitgetError("No closed 1H candles returned")
            signals = detect_formal_signals(symbol, candles, state.setdefault(symbol, {}))
            report["signals"].extend(s for s in signals if datetime.fromtimestamp(s["candle_timestamp_ms"] / 1000, tz=tz).date() == today)
            item["timeframes"][GRANULARITY] = {"candles_received": len(candles), "closed_candles": len(closed), "latest_closed_candle_ms": closed[-1]["timestamp_ms"], "latest_closed_price": closed[-1]["close"]}
            item.update({"data_available": True, "excluded_reason": None})
            report["symbols_ok"] += 1
        except Exception as exc:
            item["timeframes"][GRANULARITY] = {"error": str(exc)}
            item.update({"data_available": False, "excluded_reason": str(exc)})
            report["symbols_excluded"] += 1
        report["results"].append(item)
    # Persist every formal signal seen today so each scan can notify the full daily set.
    daily_by_key = {
        (str(s.get("symbol")), int(s.get("candle_timestamp_ms", 0)), str(s.get("filter_side"))): s
        for s in daily_signals if isinstance(s, dict)
    }
    for signal in report["signals"]:
        daily_by_key[(str(signal.get("symbol")), int(signal.get("candle_timestamp_ms", 0)), str(signal.get("filter_side")))] = signal
    daily_state = {"date": today.isoformat(), "signals": list(daily_by_key.values())}
    state["__daily_formal_signals__"] = daily_state
    report["signals"] = daily_state["signals"]
    save_state(state)
    return report

def main() -> int:
    report = scan_market_data()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    path = os.environ.get("V9_REPORT_PATH", "v9/scan-report.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(rendered + "\n")
    return 0 if report["symbols_ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
