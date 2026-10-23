"""VEGAS V9 cumulative signal notifications via Bark only."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from typing import Any

STATE_PATH = os.environ.get("V9_LAST_SIGNALS_PATH", "v9/.last-signals.json")

def display_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("USDT"):
        value = value[:-4]
    return "CL" if value == "CLU" else value

def signal_key(signal: dict[str, Any]) -> str:
    return "|".join(str(signal.get(k, "")) for k in ("symbol", "direction", "signal_type", "candle_timestamp_ms"))

def load_previous() -> list[dict[str, Any]]:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [x for x in data.get("signals", []) if isinstance(x, dict)] if isinstance(data, dict) else []
    except (OSError, json.JSONDecodeError):
        return []

def save_signals(signals: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"signals": signals}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, STATE_PATH)

def send_notification(report_path: str) -> int:
    bark_key = os.environ.get("V9_BARK_KEY", "").strip()
    if not bark_key:
        print("ERROR: V9_BARK_KEY must be configured.", file=sys.stderr)
        return 1
    with open(report_path, encoding="utf-8") as f:
        report: dict[str, Any] = json.load(f)
    current = [x for x in report.get("signals", []) if isinstance(x, dict) and x.get("formal_signal") is True]
    previous = load_previous()
    combined: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for signal in previous + current:
        key = signal_key(signal)
        if key not in seen_keys:
            combined.append(signal)
            seen_keys.add(key)
    symbols: list[str] = []
    seen_symbols: set[str] = set()
    for signal in combined:
        symbol = display_symbol(str(signal.get("symbol", "")))
        if symbol and symbol not in seen_symbols:
            symbols.append(symbol)
            seen_symbols.add(symbol)
    core_order = ["BTC", "HYPE", "XAU", "CL", "SNDK"]
    stock_order = ["NVDA","AAPL","MSFT","AMZN","GOOGL","META","TSLA","AVGO","AMD","HOOD","GLW","SPCX","CRCL","MSTR","COIN","PLTR","ORCL","INTC","MU","MRVL","ASML","ARM","APP","RDDT","NFLX","BABA","JD","QCOM","TXN","AMAT","LRCX","KLAC","JPM","GS","BAC","WFC","XOM","CVX","CAT","GE","CEG","UBER","DASH","SHOP","CRM","NOW","PANW","CRWD","TSM"]
    core = [s for s in core_order if s in seen_symbols]
    stocks = [s for s in stock_order if s in seen_symbols]
    known = set(core_order) | set(stock_order)
    stocks.extend(s for s in symbols if s not in known)
    parts = []
    if stocks:
        parts.append("🔔 美股巨头\n" + "\n".join("   ".join(f"▰ {s} ▰" for s in stocks[i:i+3]) for i in range(0, len(stocks), 3)))
    if core:
        parts.append("🔔 核心能源\n" + "   ".join(f"▰ {s} ▰" for s in core))
    new_keys = {signal_key(x) for x in current}
    old_count = sum(1 for x in combined if signal_key(x) not in new_keys)
    body = (f"累计正式信号：{len(combined)} 条；本轮新增：{len(current)} 条；历史保留：{old_count} 条。\n\n" + "\n\n".join(parts)) if combined else "本轮没有正式新信号，上一轮也没有可重复推送的信号。"
    test = os.environ.get("V9_NOTIFICATION_TEST_MODE") == "1"
    if test:
        body = "【测试推送】\n" + body
    payload = json.dumps({"device_key": bark_key, "title": "【测试推送】VEGAS V9 SIGNAL SYSTEM" if test else "VEGAS V9 SIGNAL SYSTEM", "body": body, "group": "VEGAS V9", "level": "active"}, ensure_ascii=False).encode()
    try:
        req = urllib.request.Request("https://api.day.app/push", data=payload, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Bark HTTP {response.status}")
            print(f"Bark accepted notification (HTTP {response.status}); cumulative signals: {len(combined)}.")
        save_signals(combined)
        return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
