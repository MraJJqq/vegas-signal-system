"""Send approved formal V7 signal notifications to ntfy.

This module intentionally refuses to send market scans, touches, or empty
signal lists. Only records explicitly marked formal_signal=true are eligible.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def send_formal_signals(report_path: str) -> int:
    topic = os.environ.get("V7_NTFY_TOPIC", "").strip()
    if not topic:
        print("V7_NTFY_TOPIC is not configured; no notification sent.")
        return 0

    with open(report_path, "r", encoding="utf-8") as file:
        report: dict[str, Any] = json.load(file)

    signals = [
        signal for signal in report.get("signals", [])
        if isinstance(signal, dict) and signal.get("formal_signal") is True
    ]
    if not signals:
        print("No formal V7 signals; no notification sent.")
        return 0

    message_lines = ["VEGAS V7 正式信号"]
    for signal in signals:
        symbol = str(signal.get("symbol", "未知品种"))
        direction = str(signal.get("direction", "方向待确认"))
        timeframe = str(signal.get("timeframe", "周期待确认"))
        close_price = signal.get("close_price", "未提供")
        message_lines.append(
            f"{symbol}｜{direction}｜{timeframe}｜收盘价 {close_price}"
        )
    body = "\n".join(message_lines).encode("utf-8")

    request = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body,
        headers={
            "Title": "VEGAS V7 正式信号",
            "Priority": "high",
            "Tags": "chart_with_upwards_trend",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"ntfy returned HTTP {response.status}")
            print(f"ntfy notification accepted (HTTP {response.status}).")
            return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "v7/scan-report.json"
    sys.exit(send_formal_signals(path))
