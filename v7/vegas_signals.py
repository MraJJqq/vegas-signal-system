"""Approved V7 Vegas signal detection for closed 4H candles."""
from __future__ import annotations

from typing import Any


def ema(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period < 1:
        raise ValueError("period must be positive")
    if len(values) < period:
        return result
    previous = sum(values[:period]) / period
    result[period - 1] = previous
    alpha = 2.0 / (period + 1)
    for i in range(period, len(values)):
        previous = values[i] * alpha + previous * (1.0 - alpha)
        result[i] = previous
    return result


def detect_formal_signals(symbol: str, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check the latest closed candle; each Vegas line is evaluated independently."""
    closed = sorted(
        (c for c in candles if c.get("closed")),
        key=lambda c: c["timestamp_ms"],
    )
    if not closed:
        return []
    closes = [float(c["close"]) for c in closed]
    filters = ema(closes, 12)
    last = closed[-1]
    filter_value = filters[-1]
    if filter_value is None:
        return []
    signals = []
    for label, period in (("中锋EMA144", 144), ("中锋EMA169", 169),
                          ("红峰EMA576", 576), ("红峰EMA676", 676)):
        line_values = ema(closes, period)
        line_value = line_values[-1]
        if line_value is None or not (float(last["low"]) <= line_value <= float(last["high"])):
            continue
        close = float(last["close"])
        if close > filter_value:
            direction = "LONG"
        elif close < filter_value:
            direction = "SHORT"
        else:
            continue
        signals.append({
            "symbol": symbol,
            "timeframe": "4H",
            "direction": direction,
            "line": label,
            "line_value": line_value,
            "filter": "EMA12",
            "filter_value": filter_value,
            "close": close,
            "candle_timestamp_ms": last["timestamp_ms"],
        })
    return signals
