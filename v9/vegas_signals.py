"""VEGAS V9 signal rules; intentionally inherited from V8."""
from __future__ import annotations
from typing import Any

LINES = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
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

def detect_formal_signals(symbol: str, candles: list[dict[str, Any]], state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
        # Formal confirmation must be on a strictly later 1H candle than the touch candle.
        is_after_touch = touch_timestamp_ms is not None and timestamp_ms > int(touch_timestamp_ms)
        if observing and is_after_touch and filter_value is not None:
            close_price = float(candle["close"])
            side = "上方" if close_price > filter_value else "下方" if close_price < filter_value else None
            if side is not None:
                signals.append({"formal_signal": True, "symbol": symbol, "timeframe": "1H", "line": ", ".join(touched_lines), "touch_timestamp_ms": touch_timestamp_ms, "filter_line": "EMA12", "filter_side": side, "filter_value": filter_value, "close_price": close_price, "candle_timestamp_ms": timestamp_ms})
                observing, touched_lines, touch_timestamp_ms = False, [], None
                last_processed = timestamp_ms
                continue
        if not observing:
            hit_lines = [label for label, _period in LINES if values[label][index] is not None and low <= values[label][index] <= high]
            if hit_lines:
                observing, touched_lines = True, hit_lines
                touch_timestamp_ms = timestamp_ms
        last_processed = timestamp_ms
    state.update({"observing": observing, "touched_lines": touched_lines, "touch_timestamp_ms": touch_timestamp_ms, "last_processed_timestamp_ms": last_processed})
    return signals
