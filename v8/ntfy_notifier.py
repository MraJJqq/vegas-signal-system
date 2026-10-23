"""Send V8 notifications using the approved compact grouped layout."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def display_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("USDT"):
        value = value[:-4]
    if value == "CLU":
        return "CL"
    return value


def send_notification(report_path: str) -> int:
    topic = os.environ.get("V8_NTFY_TOPIC", "").strip()
    bark_key = os.environ.get("V8_BARK_KEY", "").strip()
    if not topic:
        print("ERROR: V8_NTFY_TOPIC is not configured.", file=sys.stderr)
        return 1
    if not bark_key:
        print("ERROR: V8_BARK_KEY is not configured.", file=sys.stderr)
        return 1
    token = os.environ.get("V8_NTFY_TOKEN", "").strip()

    with open(report_path, "r", encoding="utf-8") as file:
        report: dict[str, Any] = json.load(file)

    signals = [
        item for item in report.get("signals", [])
        if isinstance(item, dict) and item.get("formal_signal") is True
    ]

    symbols: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        symbol = display_symbol(str(signal.get("symbol", "")))
        if symbol and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)

    if not symbols:
        print("No formal signals found; no notification sent.")
        return 0

    # Every scan sends all formal signals found in that scan; no change comparison.
    core_order = ["BTC", "HYPE", "XAU", "CL", "SNDK"]
    stock_order = [
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META",
        "TSLA", "AVGO", "AMD", "HOOD", "GLW", "SPCX", "CRCL",
        "MSTR", "COIN", "PLTR", "ORCL", "INTC", "MU", "MRVL",
        "ASML", "ARM", "APP", "RDDT", "NFLX", "BABA", "JD",
        "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "JPM", "GS", "BAC",
        "WFC", "XOM", "CVX", "CAT", "GE", "CEG", "UBER", "DASH",
        "SHOP", "CRM", "NOW", "PANW", "CRWD", "TSM"
    ]
    core = [symbol for symbol in core_order if symbol in seen]
    stocks = [symbol for symbol in stock_order if symbol in seen]
    known = set(core_order) | set(stock_order)
    stocks.extend(symbol for symbol in symbols if symbol not in known)

    sections: list[str] = ["VEGAS V8 SIGNAL SYSTEM"]
    if stocks:
        stock_lines = [
            "   ".join(f"▰ {symbol} ▰" for symbol in stocks[i:i + 3])
            for i in range(0, len(stocks), 3)
        ]
        sections.append("🔔 美股巨头\n" + "\n".join(stock_lines))
    if core:
        sections.append("🔔 核心能源\n" + "   ".join(
            f"▰ {symbol} ▰" for symbol in core
        ))
    message = "\n\n".join(sections)
    test_mode = os.environ.get("V8_NOTIFICATION_TEST_MODE") == "1"
    if test_mode:
        message = "【测试推送】\n" + message

    ntfy_payload = json.dumps(
        {"topic": topic, "message": message, "priority": 4},
        ensure_ascii=False,
    ).encode("utf-8")
    ntfy_headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        ntfy_headers["Authorization"] = f"Bearer {token}"
    try:
        request = urllib.request.Request(
            "https://ntfy.sh/", data=ntfy_payload, headers=ntfy_headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"ntfy returned HTTP {response.status}")
            print(f"ntfy accepted notification (HTTP {response.status}).")
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        ntfy_ok = False
    else:
        ntfy_ok = True

    # Bark already renders its title separately; omit the heading from its body.
    bark_body = message
    if test_mode and bark_body.startswith("【测试推送】\n"):
        bark_body = bark_body[len("【测试推送】\n"):]
    if bark_body.startswith("VEGAS V8 SIGNAL SYSTEM"):
        bark_body = bark_body[len("VEGAS V8 SIGNAL SYSTEM"):].lstrip("\n")

    bark_payload = json.dumps(
        {
            "device_key": bark_key,
            "title": "【测试推送】VEGAS V8 SIGNAL SYSTEM" if test_mode else "VEGAS V8 SIGNAL SYSTEM",
            "body": bark_body,
            "group": "VEGAS V8",
            "level": "active",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        request = urllib.request.Request(
            "https://api.day.app/push",
            data=bark_payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Bark returned HTTP {response.status}")
            print(f"Bark accepted notification (HTTP {response.status}); symbols: {', '.join(symbols)}.")
            bark_ok = True
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"Bark notification failed: {exc}", file=sys.stderr)
        bark_ok = False

    if ntfy_ok and bark_ok:
        print("Both notification channels succeeded.")
        return 0
    print("ERROR: one or more notification channels failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
