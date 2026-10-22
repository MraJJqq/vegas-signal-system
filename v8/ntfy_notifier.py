"""Send compact V8 notifications with a concise title and symbol list."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


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
        symbol = str(signal.get("symbol", "")).strip()
        if symbol and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)

    if symbols:
        title = f"VEGAS V8｜正式交易信号（{len(symbols)}）"
        message = "\n".join(symbols)
        priority = 4
    else:
        title = "VEGAS V8｜本轮无正式信号"
        message = "本轮暂无符合信号的标的"
        priority = 3

    # Keep the body text-only and compact. Font, color, and background are
    # controlled by the ntfy client/OS and cannot be set by this payload.
    payload = json.dumps(
        {
            "topic": topic,
            "title": title,
            "message": message,
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
