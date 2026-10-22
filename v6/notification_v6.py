"""V6 formal-signal formatting and ntfy delivery."""
from __future__ import annotations
import os
import time
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

def send_ntfy(message: str, *, topic: str | None = None) -> None:
    """Send formal V6 signal notifications to the configured ntfy topic."""
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        raise RuntimeError("NTFY_TOPIC is not configured")
    if any(ch.isspace() for ch in topic) or "/" in topic:
        raise ValueError("Invalid ntfy topic")
    request = Request(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={"Title": "VEGAS V6 SIGNAL", "Priority": "high", "Tags": "chart_with_upwards_trend"},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8", errors="replace")
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"ntfy returned HTTP {response.status}: {body}")
            return
        except Exception as exc:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"ntfy notification failed: {exc}") from exc
