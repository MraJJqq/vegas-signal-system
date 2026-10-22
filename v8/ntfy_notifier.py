""""Send clean V8 scan notifications through ntfy."""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

def _scan_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "未提供"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
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
    signals = [x for x in report.get("signals", []) if isinstance(x, dict) and x.get("formal_signal") is True]
    scan_time = _scan_time(report.get("started_at_utc"))
    total = report.get("symbols_total", 0)
    ok = report.get("symbols_ok", 0)
    excluded = report.get("symbols_excluded", 0)
    if signals:
        title = f"VEGAS V8 | {len(signals)} Formal Signal(s)"
        lines = ["VEGAS V8  |  正式交易信号", "BITGET PERPETUAL  ·  4H", ""]
        for i, signal in enumerate(signals, 1):
            lines.extend([f"{i:02d}  {signal.get('symbol', '未知品种')}", f"触碰均线  {signal.get('line', '均线未知')}", f"周期      {signal.get('timeframe', '4H')}", f"收盘价    {signal.get('close_price', '未提供')}", ""])
        lines.extend(["VEGAS V8  ·  已收盘K线确认", f"扫描时间  {scan_time}"])
        priority, tags = "high", "chart_with_upwards_trend"
    else:
        title = "VEGAS V8 | Scan Complete"
        lines = ["VEGAS V8  |  扫描完成", "", "本轮没有正式信号。", "", f"扫描品种  {ok}/{total}", f"数据异常  {excluded}", f"扫描时间  {scan_time}", "", "VEGAS V8  ·  BITGET PERPETUAL"]
        priority, tags = "default", "white_check_mark"
    request = urllib.request.Request(f"https://ntfy.sh/{topic}", data="\n".join(lines).encode("utf-8"), headers={"Title": title, "Priority": priority, "Tags": tags, "Content-Type": "text/plain; charset=utf-8", **({"Authorization": f"Bearer {token}"} if token else {})}, method="POST")
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
