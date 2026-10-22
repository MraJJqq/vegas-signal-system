"""VEGAS V6 signal rules. Only closed 4H candles can confirm signals."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

TIMEFRAME = "4H"

@dataclass(frozen=True)
class Candle:
    close: float
    high: float
    low: float
    closed: bool = True

@dataclass(frozen=True)
class SignalEvent:
    observation: str
    direction: str
    close: float
    filter_ema: float

@dataclass
class WatchStates:
    midline: bool = False
    red_peak: bool = False

def _touches(candle: Candle, a: float, b: float) -> bool:
    lower, upper = sorted((a, b))
    return (candle.high >= lower and candle.low <= upper) or lower <= candle.close <= upper

def _direction(close: float, filter_ema: float) -> Optional[str]:
    if close < filter_ema:
        return "SHORT"
    if close > filter_ema:
        return "LONG"
    return None

def evaluate_candle(candle: Candle, ema12: float, ema144: float, ema169: float,
                    ema576: float, ema676: float, states: WatchStates) -> list[SignalEvent]:
    """Touch starts an observation; only a later closed candle can confirm it."""
    if not candle.closed:
        return []
    was_midline_active = states.midline
    was_red_peak_active = states.red_peak

    if _touches(candle, ema144, ema169):
        states.midline = True
    if _touches(candle, ema576, ema676):
        states.red_peak = True

    direction = _direction(candle.close, ema12)
    events: list[SignalEvent] = []
    if was_midline_active and states.midline and direction:
        events.append(SignalEvent("midline", direction, candle.close, ema12))
        states.midline = False
    if was_red_peak_active and states.red_peak and direction:
        events.append(SignalEvent("red_peak", direction, candle.close, ema12))
        states.red_peak = False
    return events
