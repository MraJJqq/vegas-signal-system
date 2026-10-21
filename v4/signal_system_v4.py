"""Vegas Signal System V4 core rules.

Rule source: VEGAS_SIGNAL_SYSTEM_V4.md.
Pure logic only: callers supply closed candles and computed EMA values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

ALLOWED_TIMEFRAMES = ("4H",)
MIDLINE_PERIODS = (144, 169)
RED_PEAK_PERIODS = (576, 676)
FILTER_PERIOD = 12


@dataclass(frozen=True)
class Candle:
    close: float
    high: float
    low: float
    closed: bool = True


@dataclass(frozen=True)
class SignalEvent:
    timeframe: str
    direction: str
    close: float
    filter_ema: float
    reason: str = "closed candle confirmed on EMA12 side"


@dataclass
class WatchState:
    active: bool = False


def _bounds(a: float, b: float) -> tuple[float, float]:
    return min(a, b), max(a, b)


def _overlaps_band(candle: Candle, a: float, b: float) -> bool:
    lower, upper = _bounds(a, b)
    return candle.high >= lower and candle.low <= upper


def _inside_or_touches_band(candle: Candle, a: float, b: float) -> bool:
    lower, upper = _bounds(a, b)
    return _overlaps_band(candle, a, b) or lower <= candle.close <= upper


def _direction(close: float, ema144: float, ema169: float) -> Optional[str]:
    lower, upper = _bounds(ema144, ema169)
    if close > upper:
        return "LONG"
    if close < lower:
        return "SHORT"
    return None


def evaluate_candle(
    timeframe: str,
    candle: Candle,
    ema12: float,
    ema144: float,
    ema169: float,
    state: WatchState,
    ema576: Optional[float] = None,
    ema676: Optional[float] = None,
) -> Optional[SignalEvent]:
    """Advance observation state and emit at most one event per eligible candle."""
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use 4H only.")
    if not candle.closed:
        return None

    was_observing = state.active
    midline_trigger = _inside_or_touches_band(candle, ema144, ema169)
    red_peak_trigger = (
        ema576 is not None and ema676 is not None
        and _inside_or_touches_band(candle, ema576, ema676)
    )
    if midline_trigger or red_peak_trigger:
        state.active = True

    if not state.active or not was_observing:
        return None

    direction = _direction(candle.close, ema144, ema169)
    if direction == "LONG" and candle.close > ema12:
        state.active = False
        return SignalEvent(timeframe, direction, candle.close, ema12)
    if direction == "SHORT" and candle.close < ema12:
        state.active = False
        return SignalEvent(timeframe, direction, candle.close, ema12)
    return None


def scan_closed_candles(timeframe: str, rows: Iterable[tuple]) -> list[SignalEvent]:
    """Process chronological tuples: candle, EMA12, EMA144, EMA169[, EMA576, EMA676]."""
    state = WatchState()
    events: list[SignalEvent] = []
    for row in rows:
        if len(row) == 4:
            candle, ema12, ema144, ema169 = row
            ema576 = ema676 = None
        elif len(row) == 6:
            candle, ema12, ema144, ema169, ema576, ema676 = row
        else:
            raise ValueError("Rows must have 4 fields, or 6 fields including EMA576/EMA676.")
        event = evaluate_candle(
            timeframe, candle, ema12, ema144, ema169, state, ema576, ema676
        )
        if event is not None:
            events.append(event)
    return events
