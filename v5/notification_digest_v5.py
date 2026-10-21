"""V5 ntfy delivery and same-local-day signal digest; isolated from prior versions."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ConfirmedSignal:
    signal_id: str
    symbol: str
    direction: str
    timeframe: str
    candle_time: str
    close: float

    @classmethod
    def from_closed_candle(
        cls, *, symbol: str, direction: str, timeframe: str,
        candle_time: str, close: float,
    ) -> "ConfirmedSignal":
        normalized_symbol = symbol.strip().upper()
        normalized_direction = direction.strip().upper()
        normalized_timeframe = timeframe.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if normalized_direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        if normalized_timeframe != "4H":
            raise ValueError("V5 signals must use 4H")
        if close <= 0:
            raise ValueError("close must be positive")
        signal_id = "|".join((normalized_symbol, normalized_timeframe, candle_time, normalized_direction))
        return cls(signal_id, normalized_symbol, normalized_direction,
                   normalized_timeframe, candle_time, float(close))


def load_daily_state(path: str | Path, local_day: date) -> dict:
    """Load today's signal IDs; discard prior-day digest after date rollover."""
    state_path = Path(path)
    if not state_path.exists():
        return {"local_day": local_day.isoformat(), "signals": []}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read V5 notification state: {exc}") from exc
    if loaded.get("local_day") != local_day.isoformat():
        return {"local_day": local_day.isoformat(), "signals": []}
    signals = loaded.get("signals")
    if not isinstance(signals, list):
        raise ValueError("V5 notification state signals must be a list")
    return {"local_day": local_day.isoformat(), "signals": signals}


def update_daily_digest(
    state: dict, confirmed_signals: Iterable[ConfirmedSignal], local_day: date
) -> tuple[dict, list[ConfirmedSignal]]:
    """Merge confirmed signals by stable ID and return only genuinely new events."""
    if state.get("local_day") != local_day.isoformat():
        state = {"local_day": local_day.isoformat(), "signals": []}
    existing = {item["signal_id"] for item in state.get("signals", [])}
    new_events: list[ConfirmedSignal] = []
    signals = list(state.get("signals", []))
    for signal in confirmed_signals:
        if signal.signal_id in existing:
            continue
        signals.append(asdict(signal))
        existing.add(signal.signal_id)
        new_events.append(signal)
    signals.sort(key=lambda item: (item["candle_time"], item["symbol"], item["direction"]))
    return {"local_day": local_day.isoformat(), "signals": signals}, new_events


def save_daily_state(path: str | Path, state: dict) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(state_path)


def format_digest(state: dict, new_events: Iterable[ConfirmedSignal]) -> str:
    """Format the daily signal digest."""
    daily = state.get("signals", [])
    new_events = list(new_events)
    divider = "━━━━━━━━━━━━━━━━"
    sections = [divider]
    if not daily:
        sections.append("当前无正式信号")
    else:
        seen = set()
        for item in daily:
            symbol = item["symbol"]
            direction = item["direction"]
            key = (symbol, direction)
            if key in seen:
                continue
            seen.add(key)
            direction_line = "▲ LONG   🟢" if direction == "LONG" else "▼ SHORT   🔴"
            sections.extend((f"{symbol}   {direction_line}", divider))
        if sections[-1] == divider:
            sections.pop()
    if not new_events:
        sections.extend((divider, "本次没有新信号"))
    return "\n".join(sections)


def send_ntfy(message: str, *, topic: str | None = None, server: str | None = None) -> None:
    """Send a message to ntfy using the configured topic and optional base URL."""
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        raise RuntimeError("NTFY_TOPIC is not configured")
    if "/" in topic or topic.strip() != topic:
        raise ValueError("NTFY_TOPIC must be a topic name, not a URL or padded value")
    server = server or os.environ.get("NTFY_BASE_URL") or "https://ntfy.sh"
    request = Request(
        f"{server.rstrip('/')}/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": "VEGAS V5 SIGNAL",
            "Priority": "high",
            "Tags": "green_circle,red_circle",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=15) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"ntfy returned HTTP {response.status}")
            return
        except Exception as exc:
            status = getattr(exc, "code", None)
            if status == 429 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"ntfy delivery failed: {exc}") from exc
