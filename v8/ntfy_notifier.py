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

    now = datetime.now(CHINA_TZ)
    today = now.date().isoformat()
    previous_state = read_state()
    previous_symbols = previous_state.get("symbols", [])
    if not isinstance(previous_symbols, list):
        previous_symbols = []
    previous_symbols = [
        display_symbol(str(symbol))
        for symbol in previous_symbols
        if str(symbol).strip()
    ]

    first_scan_today = previous_state.get("date") != today
    if first_scan_today:
        previous_symbols = []

    previous_seen = set(previous_symbols)
    has_new_symbol = bool(set(symbols) - previous_seen)
    show_symbols = first_scan_today or has_new_symbol

    daily_symbols = list(previous_symbols)
    daily_seen = set(daily_symbols)
    for symbol in symbols:
        if symbol not in daily_seen:
            daily_symbols.append(symbol)
            daily_seen.add(symbol)

    display_symbols = daily_symbols if show_symbols else []
    core_order = ["BTC", "HYPE", "XAU", "CL"]
    core = [symbol for symbol in core_order if symbol in display_symbols]
    stocks = [symbol for symbol in display_symbols if symbol not in core_order]

    core_section = "🔔 核心能源"
    if show_symbols and core:
        core_section += "\n" + "   ".join(f"▰ {symbol} ▰" for symbol in core)
    else:
        core_section += "\n▰ No change ▰"

    stock_section = "🔔 美股巨头"
    if show_symbols and stocks:
        stock_lines = [
            "   ".join(f"▰ {symbol} ▰" for symbol in stocks[i:i + 3])
            for i in range(0, len(stocks), 3)
        ]
        stock_section += "\n" + "\n".join(stock_lines)
    else:
        stock_section += "\n▰ No change ▰"

    footer_title = "VEGAS V8 SIGNAL SYSTEM"
    message = (
        footer_title + "\n\n" + stock_section + "\n\n" + core_section
    )
    priority = 4 if symbols else 3

    ntfy_payload = json.dumps(
        {"topic": topic, "message": message, "priority": priority},
        ensure_ascii=False,
    ).encode("utf-8")
    ntfy_headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        ntfy_headers["Authorization"] = f"Bearer {token}"

    ntfy_ok = False
    bark_ok = False
    try:
        request = urllib.request.Request(
            "https://ntfy.sh/", data=ntfy_payload, headers=ntfy_headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"ntfy returned HTTP {response.status}")
            ntfy_ok = True
            print(f"ntfy accepted notification (HTTP {response.status}).")
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)

    bark_payload = json.dumps(
        {
            "device_key": bark_key,
            "title": "",
            "body": message,
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
            bark_ok = True
            print(f"Bark accepted notification (HTTP {response.status}).")
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"Bark notification failed: {exc}", file=sys.stderr)

    # Only advance comparison state when both channels accepted this notification.
    # If one channel fails, the next scheduled run retries the same daily list.
    if ntfy_ok and bark_ok:
        save_state(today, daily_symbols)
        mode = "full daily list" if show_symbols else "no change"
        print(f"Both notification channels succeeded ({mode}).")
        return 0

    print("ERROR: one or more notification channels failed; state was not advanced.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
