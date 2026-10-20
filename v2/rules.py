"""Pure rule functions for Vegas Signal System V2.

No network access, notification side effects, or order placement in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class EntryDecision:
    status: str
    direction: str | None
    observation_active: bool
    signal_timestamp: str | None = None
    reason: str = ""


def candle_touches_ema144(candle: Mapping[str, Any]) -> bool:
    """A completed candle touches EMA144 when low <= EMA144 <= high."""
    try:
        low = float(candle["low"])
        high = float(candle["high"])
        ema = float(candle["ema144"])
    except (KeyError, TypeError, ValueError):
        return False
    if low > high:
        return False
    return low <= ema <= high


def evaluate_entry(
    candles: Iterable[Mapping[str, Any]],
    direction_gate: str,
    observation_active: bool = False,
) -> EntryDecision:
    """Evaluate completed entry-timeframe candles, oldest to newest.

    A touch activates observation but never emits a signal by itself.
    Once observing, the latest completed candle must close strictly on the
    correct side of EMA12. Equality produces no signal.
    """
    rows = list(candles)
    gate = str(direction_gate).lower()
    if gate not in {"up", "down"}:
        return EntryDecision(
            status="BLOCKED_DIRECTION",
            direction=None,
            observation_active=observation_active,
            reason="4H direction is unavailable or not valid",
        )
    if not rows:
        return EntryDecision(
            status="NO_DATA",
            direction=None,
            observation_active=observation_active,
            reason="No completed entry candles",
        )

    active = bool(observation_active)
    for row in rows:
        if row.get("complete", True) and candle_touches_ema144(row):
            active = True

    latest = rows[-1]
    if not latest.get("complete", True):
        return EntryDecision(
            status="INCOMPLETE_CANDLE",
            direction=None,
            observation_active=active,
            reason="Latest candle is not complete",
        )

    if not active:
        return EntryDecision(
            status="WAIT_MIDLINE_TOUCH",
            direction=None,
            observation_active=False,
            reason="No EMA144 touch has been observed",
        )

    try:
        close = float(latest["close"])
        ema12 = float(latest["ema12"])
    except (KeyError, TypeError, ValueError):
        return EntryDecision(
            status="WAIT_FILTER_CLOSE",
            direction=None,
            observation_active=True,
            reason="Latest completed candle is missing close or EMA12",
        )

    timestamp = str(latest.get("timestamp", "")) or None
    if gate == "up" and close > ema12:
        return EntryDecision(
            status="ENTRY_SIGNAL_LONG",
            direction="long",
            observation_active=True,
            signal_timestamp=timestamp,
            reason="4H direction is up; observation active; close above EMA12",
        )
    if gate == "down" and close < ema12:
        return EntryDecision(
            status="ENTRY_SIGNAL_SHORT",
            direction="short",
            observation_active=True,
            signal_timestamp=timestamp,
            reason="4H direction is down; observation active; close below EMA12",
        )
    return EntryDecision(
        status="WAIT_FILTER_CLOSE",
        direction=None,
        observation_active=True,
        reason="EMA12 close confirmation has not occurred",
    )
