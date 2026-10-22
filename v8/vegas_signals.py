"""VEGAS V8 signal rules."""
from __future__ import annotations

from typing import Any


LINES = (
    ("中锋EMA144", 144),
    ("中锋EMA169", 169),
    ("红峰EMA576", 576),
    ("红峰EMA676", 676),
)
FILTER_PERIOD = 12


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
    """Touch a 4H 中锋/红峰 line to enter unlimited observation.

    A formal signal is emitted only on a later closed 4H candle whose close
    is strictly above or below EMA12. Touching and filter confirmation cannot
    occur on the same candle. After a formal signal, observation resets.
    """
    closed = sorted(
        (c for c in candles if c.get("closed")),
        key=lambda c: c["timestamp_ms"],
    )
    if not closed:
        return []

    closes = [float(c["close"]) for c in closed]
    values = {label: ema(closes, period) for label, period in LINES}
    filter_values = ema(closes, FILTER_PERIOD)
    observing = False
    touched_lines: list[str] = []
    touch_timestamp_ms: int | None = None
    signals: list[dict[str, Any]] = []

    for index, candle in enumerate(closed):
        filter_value = filter_values[index]
        high, low = float(candle["high"]), float(candle["low"])

        if observing:
            if filter_value is not None:
                close_price = float(candle["close"])
                if close_price > filter_value or close_price < filter_value:
                    side = "上方" if close_price > filter_value else "下方"
                    signals.append({
                        "formal_signal": True,
                        "symbol": symbol,
                        "timeframe": "4H",
                        "line": ", ".join(touched_lines),
                        "touch_timestamp_ms": touch_timestamp_ms,
                        "filter_line": "EMA12",
                        "filter_side": side,
                        "filter_value": filter_value,
                        "close_price": close_price,
                        "candle_timestamp_ms": int(candle["timestamp_ms"]),
                    })
                    observing = False
                    touched_lines = []
                    touch_timestamp_ms = None
                    continue

        # Only enter observation when not already observing. This ensures the
        # touch candle itself cannot also become the formal-signal candle.
        if not observing:
            hit_lines = []
            for label, _period in LINES:
                line_value = values[label][index]
                if line_value is not None and low <= line_value <= high:
                    hit_lines.append(label)
            if hit_lines:
                observing = True
                touched_lines = hit_lines
                touch_timestamp_ms = int(candle["timestamp_ms"])

    return signals
