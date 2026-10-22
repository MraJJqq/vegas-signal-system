"""Send V7 scan status and formal signal notifications to ntfy.

Formal signals are included when present. A successful scan with no formal
signals still sends a status notification so the user knows the scan ran.
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
        print("ERROR: V7_NTFY_TOPIC is not configured; no notification sent.", file=sys.stderr)
        return 1

    token = os.environ.get("V7_NTFY_TOKEN", "").strip()

    with open(report_path, "r", encoding="utf-8") as file:
        report: dict[str, Any] = json.load(file)

    signals = [
        signal for signal in report.get("signals", [])
        if isinstance(signal, dict) and signal.get("formal_signal") is True
    ]
    if not signals:
        message_lines = ["VEGAS V7 扫描完成", "本轮没有正式交易信号。"]
        title = "VEGAS V7 scan complete: no formal signal"
        tags = "white_check_mark"
    else:
        message_lines = ["VEGAS V7 正式信号"]
        title = "VEGAS V7 formal signal"
        tags = "chart_with_upwards_trend"
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
            "Title": title,
            "Priority": "default" if not signals else "high",
            "Tags": tags,
            "Content-Type": "text/plain; charset=utf-8",
            **({"Authorization": f"Bearer {token}"} if token else {}),
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
