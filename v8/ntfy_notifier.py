"""Send V8 notifications using the approved compact grouped layout."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


STATE_PATH = Path(os.environ.get("V8_SCAN_STATE_PATH", "v8/.scan-state.json"))
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def display_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("USDT"):
        value = value[:-4]
    if value == "CLU":
        return "CL"
    return value


def read_state() -> dict[str, Any]:
    try:
        with STATE_PATH.open("r", encoding="utf-8") as file:
            state = json.load(file)
        return state if isinstance(state, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(day: str, symbols: list[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps({"date": day, "symbols": symbols}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(STATE_PATH)


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

    now = datetime.now(CHINA_TZ)
    today = now.date().isoformat()
    previous_state = read_state()
    previous_symbols = previous_state.get("symbols", [])
    if not isinstance(previous_symbols, list):
        previous_symbols = []
    previous_symbols = [str(symbol) for symbol in previous_symbols]

    # Each China-local day starts a fresh comparison cycle; never compare across days.
    first_scan_today = previous_state.get("date") != today
    if first_scan_today:
        previous_symbols = []
    # First scan shows all current symbols; later scans show names only if any are new.
    has_new_symbol = bool(set(symbols) - set(previous_symbols))
    show_symbols = first_scan_today or has_new_symbol

    core_order = ["BTC", "HYPE", "XAU", "CL"]
    core = [symbol for symbol in core_order if symbol in symbols]
    stocks = [symbol for symbol in symbols if symbol not in core_order]

    # Category headings are always present. When names should be hidden, show
    # only the headings (no placeholder text such as "No change").
    core_section = "🔔 核心能源"
    stock_section = "🔔 美股巨头"
    if show_symbols:
        if core:
            core_section += "\n" + "   ".join(f"▰ {symbol} ▰" for symbol in core)
        if stocks:
            stock_lines = [
                "   ".join(f"▰ {symbol} ▰" for symbol in stocks[i:i + 3])
                for i in range(0, len(stocks), 3)
            ]
            stock_section += "\n" + "\n".join(stock_lines)

    message = (
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        + core_section + "\n\n" + stock_section
        + "\n\n━━━━━━━━━━━━━━━━━━━━\n本轮扫描结束"
    )
    priority = 4 if symbols else 3

    payload = json.dumps(
        {"topic": topic, "title": "🔔 VEGAS V8 信号系统 🔔", "message": message, "priority": priority},
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
            # Save the latest result only after ntfy confirms the push succeeded.
            save_state(today, symbols)
            mode = "full list" if show_symbols else "headings only"
            print(f"ntfy accepted grouped notification (HTTP {response.status}; {mode}).")
            return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
