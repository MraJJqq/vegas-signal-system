"""Approved V7 Vegas signal detection across the full returned 4H observation window."""
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
    """Scan every closed candle in the available observation window."""
    closed = sorted(
        (c for c in candles if c.get("closed")),
        key=lambda c: c["timestamp_ms"],
    )
    if not closed:
        return []
    closes = [float(c["close"]) for c in closed]
    filter_values = ema(closes, 12)
    lines = (
        ("中锋EMA144", 144),
        ("中锋EMA169", 169),
        ("红峰EMA576", 576),
        ("红峰EMA676", 676),
    )
    line_values = {label: ema(closes, period) for label, period in lines}
    signals: list[dict[str, Any]] = []
    for index, candle in enumerate(closed):
        filter_value = filter_values[index]
        if filter_value is None:
            continue
        close = float(candle["close"])
        if close > filter_value:
            direction = "LONG"
        elif close < filter_value:
            direction = "SHORT"
        else:
            continue
        for label, _period in lines:
            line_value = line_values[label][index]
            if line_value is None:
                continue
            if float(candle["low"]) <= line_value <= float(candle["high"]):
                signals.append({
                    "symbol": symbol,
                    "timeframe": "4H",
                    "direction": direction,
                    "line": label,
                    "line_value": line_value,
                    "filter": "EMA12",
                    "filter_value": filter_value,
                    "close": close,
                    "candle_timestamp_ms": candle["timestamp_ms"],
                })
    return signals
