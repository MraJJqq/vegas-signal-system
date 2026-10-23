"""VEGAS V9 grouped notifications via Bark only."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from typing import Any


def display_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("USDT"):
        value = value[:-4]
    return "CL" if value == "CLU" else value


def build_body(report: dict[str, Any]) -> tuple[str, list[str]]:
    signals = [x for x in report.get("signals", []) if isinstance(x, dict) and x.get("formal_signal") is True]
    symbols: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        symbol = display_symbol(str(signal.get("symbol", "")))
        if symbol and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    core_order = ["BTC", "HYPE", "XAU", "CL", "SNDK"]
    stock_order = ["NVDA","AAPL","MSFT","AMZN","GOOGL","META","TSLA","AVGO","AMD","HOOD","GLW","SPCX","CRCL","MSTR","COIN","PLTR","ORCL","INTC","MU","MRVL","ASML","ARM","APP","RDDT","NFLX","BABA","JD","QCOM","TXN","AMAT","LRCX","KLAC","JPM","GS","BAC","WFC","XOM","CVX","CAT","GE","CEG","UBER","DASH","SHOP","CRM","NOW","PANW","CRWD","TSM"]
    core = [symbol for symbol in core_order if symbol in seen]
    stocks = [symbol for symbol in stock_order if symbol in seen]
    known = set(core_order) | set(stock_order)
    stocks.extend(symbol for symbol in symbols if symbol not in known)
    stock_line = "\n".join("   ".join(f"▰ {symbol} ▰" for symbol in stocks[i:i+3]) for i in range(0, len(stocks), 3)) if stocks else "▰ NOCHANGE ▰"
    core_line = "   ".join(f"▰ {symbol} ▰" for symbol in core) if core else "▰ NOCHANGE ▰"
    return f"🔔 美股巨头\n{stock_line}\n\n🔔 核心能源\n{core_line}", symbols


def send_notification(report_path: str) -> int:
    bark_key = os.environ.get("V9_BARK_KEY", "").strip()
    if not bark_key:
        print("ERROR: V9_BARK_KEY must be configured.", file=sys.stderr)
        return 1
    try:
        with open(report_path, encoding="utf-8") as f:
            report: dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot read scan report: {exc}", file=sys.stderr)
        return 1
    body, symbols = build_body(report)
    test = os.environ.get("V9_NOTIFICATION_TEST_MODE") == "1"
    if test:
        body = "【测试推送】\n" + body
    payload = json.dumps({
        "device_key": bark_key,
        "title": "【测试推送】VEGAS V9 SIGNAL SYSTEM" if test else "VEGAS V9 SIGNAL SYSTEM",
        "body": body,
        "group": "VEGAS V9",
        "level": "active",
    }, ensure_ascii=False).encode()
    try:
        req = urllib.request.Request("https://api.day.app/push", data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Bark HTTP {response.status}")
            print(f"Bark accepted notification (HTTP {response.status}); symbols: {', '.join(symbols) or 'NOCHANGE'}.")
        return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
