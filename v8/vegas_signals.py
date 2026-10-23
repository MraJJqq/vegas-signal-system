""""VEGAS V8 signal rules."""
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


def detect_formal_signals(
    symbol: str,
    candles: list[dict[str, Any]],
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Detect signals while carrying observation state across scanner runs.

    The state dictionary is updated in place so the caller can persist it
    between scans and avoid losing long-lived observations or replaying bars.
    """
    closed = sorted((c for c in candles if c.get("closed")), key=lambda c: c["timestamp_ms"])
    if not closed:
        return []
    if state is None:
        state = {}
    observing = bool(state.get("observing", False))
    touched_lines = [str(line) for line in state.get("touched_lines", [])]
    touch_timestamp_ms = state.get("touch_timestamp_ms")
    last_processed = int(state.get("last_processed_timestamp_ms", -1))
    closes = [float(c["close"]) for c in closed]
    values = {label: ema(closes, period) for label, period in LINES}
    filter_values = ema(closes, FILTER_PERIOD)
    signals: list[dict[str, Any]] = []
    for index, candle in enumerate(closed):
        timestamp_ms = int(candle["timestamp_ms"])
        if timestamp_ms <= last_processed:
            continue
        filter_value = filter_values[index]
        high, low = float(candle["high"]), float(candle["low"])
        if observing and filter_value is not None:
            close_price = float(candle["close"])
            if close_price > filter_value:
                side = "上方"
            elif close_price < filter_value:
                side = "下方"
            else:
                side = None

            # EMA12 confirmation is a close-side check, not a crossover.
            # An exact equality keeps the existing observation active.
            if side is not None:
                signals.append({
                    "formal_signal": True, "symbol": symbol, "timeframe": "1H",
                    "line": ", ".join(touched_lines),
                    "touch_timestamp_ms": touch_timestamp_ms,
                    "filter_line": "EMA12", "filter_side": side,
                    "filter_value": filter_value, "close_price": close_price,
                    "candle_timestamp_ms": timestamp_ms,
                })
                observing, touched_lines, touch_timestamp_ms = False, [], None
                last_processed = timestamp_ms
                continue
        if not observing:
            hit_lines = []
            for label, _period in LINES:
                line_value = values[label][index]
                if line_value is not None and low <= line_value <= high:
                    hit_lines.append(label)
            if hit_lines:
                observing, touched_lines = True, hit_lines
                touch_timestamp_ms = timestamp_ms
        last_processed = timestamp_ms
    state.update({
        "observing": observing, "touched_lines": touched_lines,
        "touch_timestamp_ms": touch_timestamp_ms,
        "last_processed_timestamp_ms": last_processed,
    })
    return signals
