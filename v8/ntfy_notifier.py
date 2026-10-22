"""Send V8 scan result notifications through ntfy."""
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
    if signals:
        title = "VEGAS V8 Signal"
        lines = ["VEGAS V8 正式信号"]
        for signal in signals:
            lines.append(
                f"{signal.get('symbol', '未知品种')}｜"
                f"{signal.get('line', '均线未知')}｜"
                f"{signal.get('timeframe', '4H')}｜"
                f"收盘价 {signal.get('close_price', '未提供')}"
            )
        priority, tags = "high", "chart_with_upwards_trend"
    else:
        title = "VEGAS V8 Scan Complete: No Signal"
        lines = ["VEGAS V8 扫描完成", "本轮没有正式信号。"]
        priority, tags = "default", "white_check_mark"

    request = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data="\n".join(lines).encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
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
            print(f"ntfy accepted notification (HTTP {response.status}).")
            return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ntfy notification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v8/scan-report.json"))
