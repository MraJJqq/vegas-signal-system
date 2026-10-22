"""Send V8 notifications using the approved compact grouped layout."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
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
    if not topic:
        print("ERROR: V8_NTFY_TOPIC is not configured.", file=sys.stderr)
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

    title = "🔔 VEGAS V8 信号系统 🔔"
    if symbols:
        core_order = ["BTC", "HYPE", "XAU", "CL"]
        core = [symbol for symbol in core_order if symbol in symbols]
        stocks = [symbol for symbol in symbols if symbol not in core_order]
        sections: list[str] = []
        if core:
            sections.append("🔔 核心能源\n" + "   ".join(core))
        if stocks:
            sections.append("🔔 美股巨头\n" + "\n".join("   ".join(stocks[i:i + 3]) for i in range(0, len(stocks), 3)))
        message = "━━━━━━━━━━━━\n\n" + "\n\n".join(sections) + "\n\n本轮扫描结束"
        priority = 4
    else:
        message = "━━━━━━━━━━━━\n\n本轮扫描结束，没有新符合品种"
        priority = 3

    # Font, color, and background are controlled by the ntfy client/OS.
    payload = json.dumps(
        {"topic": topic, "title": title, "message": message, "priority": priority},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        "https://ntfy.sh/", data=payload, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"ntfy returned HTTP {response.status}")
            print(f"ntfy accepted grouped notification (HTTP {response.status}).")
            return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
