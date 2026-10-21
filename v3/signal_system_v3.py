"""Vegas Signal System V3.

The rule source of truth is VEGAS_SIGNAL_SYSTEM_V3.md.
Only closed 4H candles are eligible for signal confirmation.
This module deliberately does not include network fetching or notification
transport; callers provide candles and consume returned signal events.
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
    direction: Optional[str] = None


def _midline_bounds(ema144: float, ema169: float) -> tuple[float, float]:
    return min(ema144, ema169), max(ema144, ema169)


def _touches_midline(candle: Candle, ema144: float, ema169: float) -> bool:
    lower, upper = _midline_bounds(ema144, ema169)
    # The candle range overlaps the EMA144/EMA169 band.
    return candle.high >= lower and candle.low <= upper


def _inside_or_touches_band(candle: Candle, ema_a: float, ema_b: float) -> bool:
    lower, upper = min(ema_a, ema_b), max(ema_a, ema_b)
    return candle.low <= upper and candle.high >= lower or lower <= candle.close <= upper


def _direction(close: float, ema144: float, ema169: float) -> Optional[str]:
    lower, upper = _midline_bounds(ema144, ema169)
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
    """Update observation state and emit a signal only on a closed 4H candle.

    Observation starts when the candle touches/closes inside either the midline
    band (EMA144/169) or, when supplied, the red-peak band (EMA576/676).
    Direction remains determined by the midline as previously defined. While observing, a close above EMA12 confirms
    LONG only when price is above the band; a close below EMA12 confirms SHORT
    only when price is below the band. No timeout is applied.
    """
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use 4H only.")
    if not candle.closed:
        return None

    lower, upper = _midline_bounds(ema144, ema169)
    was_observing = state.active
    close_inside = lower <= candle.close <= upper
    touches_red_peak = (
        ema576 is not None and ema676 is not None
        and _inside_or_touches_band(candle, ema576, ema676)
    )
    if _touches_midline(candle, ema144, ema169) or close_inside or touches_red_peak:
        state.active = True
        state.direction = _direction(candle.close, ema144, ema169) or state.direction

    if not state.active:
        return None

    # A candle that starts observation only starts observation. It cannot
    # also produce a formal signal on that same candle.
    if not was_observing:
        return None

    direction = _direction(candle.close, ema144, ema169)
    if direction == "LONG" and candle.close > ema12:
        state.active = False
        state.direction = None
        return SignalEvent(timeframe, "LONG", candle.close, ema12)
    if direction == "SHORT" and candle.close < ema12:
        state.active = False
        state.direction = None
        return SignalEvent(timeframe, "SHORT", candle.close, ema12)
    return None


def scan_closed_candles(
    timeframe: str,
    candles: Iterable[tuple[Candle, float, float, float]],
) -> list[SignalEvent]:
    """Process chronological (candle, EMA12, EMA144, EMA169) tuples."""
    state = WatchState()
    events: list[SignalEvent] = []
    for candle, ema12, ema144, ema169 in candles:
        event = evaluate_candle(timeframe, candle, ema12, ema144, ema169, state)
        if event is not None:
            events.append(event)
    return events
