"""V6 formal-signal formatting and Server酱 Turbo personal-WeChat delivery."""
from __future__ import annotations
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

def format_signal_digest(events: list[dict]) -> str:
    divider = "━━━━━━━━━━━━━━━━"
    lines = ["🟢 🔴 VEGAS V6 SIGNAL", divider]
    seen = set()
    for event in events:
        key = (event["symbol"], event["direction"])
        if key in seen:
            continue
        seen.add(key)
        direction = "▲ LONG   🟢" if event["direction"] == "LONG" else "▼ SHORT   🔴"
        lines.extend((f'{event["symbol"]}   {direction}', divider))
    return "\n".join(lines).rstrip(divider + "\n")

def send_wechat(message: str, *, sendkey: str | None = None) -> None:
    key = sendkey or os.environ.get("SERVERCHAN_SENDKEY")
    if not key:
        raise RuntimeError("SERVERCHAN_SENDKEY is not configured")
    if not key.startswith("SCT") or any(ch.isspace() for ch in key):
        raise ValueError("Invalid Server酱 Turbo key")
    data = urlencode({"title": "VEGAS V6 SIGNAL", "desp": message}).encode()
    request = Request(f"https://sctapi.ftqq.com/{key}.send", data=data,
                      headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
                      method="POST")
    for attempt in range(4):
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                if not 200 <= response.status < 300 or result.get("code") != 0:
                    raise RuntimeError(f"Server酱 rejected notification: {result}")
            return
        except Exception as exc:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"微信推送失败: {exc}") from exc
