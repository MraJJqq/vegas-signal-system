"""VEGAS V9 signal rules: 4H observation, 1H EMA12 confirmation."""
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

def detect_formal_signals(symbol: str, candles_1h: list[dict[str, Any]], candles_4h: list[dict[str, Any]], state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Observe closed 4H touches; confirm once on a later closed 1H candle vs 1H EMA12."""
    closed_1h = sorted((c for c in candles_1h if c.get("closed")), key=lambda c: c["timestamp_ms"])
    closed_4h = sorted((c for c in candles_4h if c.get("closed")), key=lambda c: c["timestamp_ms"])
    if not closed_1h or not closed_4h:
        return []
    if state is None:
        state = {}
    observing = bool(state.get("observing", False))
    touched_lines = [str(line) for line in state.get("touched_lines", [])]
    touch_timestamp_ms = state.get("touch_timestamp_ms")
    last_processed_1h = int(state.get("last_processed_1h_timestamp_ms", -1))
    last_processed_4h = int(state.get("last_processed_4h_timestamp_ms", -1))

    closes_4h = [float(c["close"]) for c in closed_4h]
    values_4h = {label: ema(closes_4h, period) for label, period in LINES}
    closes_1h = [float(c["close"]) for c in closed_1h]
    filter_values_1h = ema(closes_1h, FILTER_PERIOD)
    signals: list[dict[str, Any]] = []

    # Observation phase: a closed 4H candle's high-low range touches any Vegas line.
    for index, candle in enumerate(closed_4h):
        ts = int(candle["timestamp_ms"])
        if ts <= last_processed_4h:
            continue
        if not observing:
            high, low = float(candle["high"]), float(candle["low"])
            hits = [label for label, _period in LINES
                    if values_4h[label][index] is not None and low <= values_4h[label][index] <= high]
            if hits:
                observing = True
                touched_lines = hits
                touch_timestamp_ms = ts
        last_processed_4h = ts

    # Signal phase: use only a later, closed 1H candle and its own 1H EMA12.
    for index, candle in enumerate(closed_1h):
        ts = int(candle["timestamp_ms"])
        if ts <= last_processed_1h:
            continue
        fv = filter_values_1h[index]
        if observing and touch_timestamp_ms is not None and ts >= int(touch_timestamp_ms) + 4 * 3600000 and fv is not None:
            close_price = float(candle["close"])
            side = "上方" if close_price > fv else "下方" if close_price < fv else None
            if side is not None:
                signals.append({
                    "formal_signal": True, "symbol": symbol, "timeframe": "1H",
                    "observation_timeframe": "4H", "phase": "信号期",
                    "line": ", ".join(touched_lines), "touch_timestamp_ms": touch_timestamp_ms,
                    "filter_line": "1H EMA12", "filter_side": side, "filter_value": fv,
                    "close_price": close_price, "candle_timestamp_ms": ts
                })
                observing, touched_lines, touch_timestamp_ms = False, [], None
        last_processed_1h = ts

    state.update({
        "observing": observing, "touched_lines": touched_lines,
        "touch_timestamp_ms": touch_timestamp_ms,
        "last_processed_1h_timestamp_ms": last_processed_1h,
        "last_processed_4h_timestamp_ms": last_processed_4h
    })
    return signals
