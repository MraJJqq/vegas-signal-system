"""VEGAS V8 signal rules."""
from __future__ import annotations

from typing import Any


LINES = (
    ("中锋EMA144", 144),
    ("中锋EMA169", 169),
    ("红峰EMA576", 576),
    ("红峰EMA676", 676),
)


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
    """A closed 4H candle touching any 中锋/红峰 EMA is a formal signal."""
    closed = sorted(
        (c for c in candles if c.get("closed")),
        key=lambda c: c["timestamp_ms"],
    )
    if not closed:
        return []

    closes = [float(c["close"]) for c in closed]
    values = {label: ema(closes, period) for label, period in LINES}
    signals: list[dict[str, Any]] = []
    for index, candle in enumerate(closed):
        high, low = float(candle["high"]), float(candle["low"])
        for label, _period in LINES:
            line_value = values[label][index]
            if line_value is None or not (low <= line_value <= high):
                continue
            signals.append({
                "formal_signal": True,
                "symbol": symbol,
                "timeframe": "4H",
                "line": label,
                "line_value": line_value,
                "close_price": float(candle["close"]),
                "candle_timestamp_ms": int(candle["timestamp_ms"]),
            })
    return signals
