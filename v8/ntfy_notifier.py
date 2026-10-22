"""Send compact V8 notifications containing only the title and symbols."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

MAX_SIGNAL_ROWS = 5


def _scan_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "未提供"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except ValueError:
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
    scan_time = _scan_time(report.get("started_at_utc"))

    if signals:
        symbols = []
        seen = set()
        for signal in signals:
            symbol = str(signal.get("symbol", "未知品种")).strip()
            if symbol and symbol not in seen:
                symbols.append(symbol)
                seen.add(symbol)
        title = f"VEGAS V8｜正式交易信号（{len(symbols)}）"
        shown = symbols[:MAX_SIGNAL_ROWS]
        lines = ["VEGAS V8", "正式交易信号", "", *shown]
        if len(symbols) > MAX_SIGNAL_ROWS:
            lines.extend(["", f"另有 {len(symbols) - MAX_SIGNAL_ROWS} 个标的"])
        priority = 4
    else:
        title = "VEGAS V8｜本轮无正式信号"
        lines = ["VEGAS V8", "正式交易信号", "", "本轮暂无符合信号的标的"]
        priority = 3

    # Keep the notification payload small and free of icons, images, and extra fields.
    payload = json.dumps(
        {
            "topic": topic,
            "title": title,
            "message": "\n".join(lines),
            "priority": priority,
        },
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
            print(f"ntfy accepted compact notification (HTTP {response.status}).")
            return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
