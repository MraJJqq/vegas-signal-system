"""VEGAS Signal System V6 core logic; only closed 4H candles are eligible."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ALLOWED_TIMEFRAMES = ("4H",)


@dataclass(frozen=True)
class Candle:
    close: float
    high: float
    low: float
    closed: bool = True


@dataclass(frozen=True)
class SignalEvent:
    observation: str
    timeframe: str
    direction: str
    close: float
    filter_ema: float


@dataclass
class WatchState:
    active: bool = False


@dataclass
class V6WatchStates:
    midline: WatchState
    red_peak: WatchState

    @classmethod
    def fresh(cls) -> "V6WatchStates":
        return cls(WatchState(), WatchState())


def _bounds(a: float, b: float) -> tuple[float, float]:
    return min(a, b), max(a, b)


def _touches(candle: Candle, a: float, b: float) -> bool:
    lower, upper = _bounds(a, b)
    return candle.high >= lower and candle.low <= upper or lower <= candle.close <= upper


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
    ema576: float,
    ema676: float,
    states: V6WatchStates,
) -> list[SignalEvent]:
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError("V6 supports 4H only")
    if not candle.closed:
        return []

    # Record which watches were already active before this candle, so a touch
    # candle itself never confirms a formal signal.
    prior_mid = states.midline.active
    prior_red = states.red_peak.active
    if _touches(candle, ema144, ema169):
        states.midline.active = True
    if _touches(candle, ema576, ema676):
        states.red_peak.active = True

    direction = _direction(candle.close, ema144, ema169)
    events: list[SignalEvent] = []
    if prior_mid and states.midline.active:
        if direction == "LONG" and candle.close > ema12:
            events.append(SignalEvent("midline", timeframe, direction, candle.close, ema12))
            states.midline.active = False
        elif direction == "SHORT" and candle.close < ema12:
            events.append(SignalEvent("midline", timeframe, direction, candle.close, ema12))
            states.midline.active = False

    if prior_red and states.red_peak.active:
        if direction == "LONG" and candle.close > ema12:
            events.append(SignalEvent("red_peak", timeframe, direction, candle.close, ema12))
            states.red_peak.active = False
        elif direction == "SHORT" and candle.close < ema12:
            events.append(SignalEvent("red_peak", timeframe, direction, candle.close, ema12))
            states.red_peak.active = False
    return events
