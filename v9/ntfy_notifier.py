"""VEGAS V9 per-symbol Bark notifications with direct Bitget links."""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.request
from typing import Any


def display_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("USDT"):
        value = value[:-4]
    return "CL" if value == "CLU" else value


CORE_ORDER = ["BTC", "HYPE", "XAU", "CL"]
STOCK_ORDER = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC", "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK", "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX"
]
ALLOWED_SYMBOLS = set(CORE_ORDER + STOCK_ORDER)


def bitget_url(symbol: str) -> str:
    """Return the Bitget USDT futures page for a normalized V9 symbol."""
    # V9 scans Bitget's CLUSDT crude-oil contract and displays it as CL.
    contract_symbol = symbol
    return f"https://www.bitget.com/futures/usdt/{contract_symbol}USDT"


def build_body(report: dict[str, Any]) -> tuple[str, list[str]]:
    signals = [x for x in report.get("signals", []) if isinstance(x, dict) and x.get("formal_signal") is True]
    symbols: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        symbol = display_symbol(str(signal.get("symbol", "")))
        # Keep the legacy safeguard: signals from symbols outside the active scan pool are ignored.
        if symbol and symbol in ALLOWED_SYMBOLS and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)

    core_set = set(CORE_ORDER)
    core = [symbol for symbol in CORE_ORDER if symbol in seen]
    other_symbols = [symbol for symbol in symbols if symbol not in core_set]
    stock_set = set(STOCK_ORDER)
    stocks = [symbol for symbol in STOCK_ORDER if symbol in other_symbols]
    stocks.extend(sorted(symbol for symbol in other_symbols if symbol not in stock_set))

    stock_line = "\n".join(
        "   ".join(f"▰ {symbol} ▰" for symbol in stocks[i:i + 3])
        for i in range(0, len(stocks), 3)
    ) if stocks else "▰ No change ▰"
    core_line = "   ".join(f"▰ {symbol} ▰" for symbol in core) if core else "▰ No change ▰"
    return f"🔸 美股巨头\n{stock_line}\n\n🔸 核心能源\n{core_line}", symbols


def _post_bark(payload: dict[str, Any]) -> None:
    req = urllib.request.Request(
        "https://api.day.app/push",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Bark HTTP {response.status}")


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
    try:
        if not symbols:
            # Preserve the existing single no-change notification when there are no formal signals.
            payload: dict[str, Any] = {
                "device_key": bark_key,
                "body": body,
                "group": "VEGAS V9",
                "level": "active",
            }
            if test:
                payload["body"] = "【测试推送】\n" + body
            _post_bark(payload)
            print("Bark accepted no-change notification (HTTP 2xx).")
        else:
            # One notification per formal signal, with its own direct Bitget contract URL.
            for symbol in symbols:
                payload = {
                    "device_key": bark_key,
                    "title": f"{'【测试推送】' if test else ''}V9 正式信号 · {symbol}",
                    "body": f"{symbol} 检测到正式信号。点击本通知打开 Bitget 对应合约。",
                    "url": bitget_url(symbol),
                    "group": "VEGAS V9",
                    "level": "active",
                }
                _post_bark(payload)
                print(f"Bark accepted notification for {symbol}: {bitget_url(symbol)}")
        return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
