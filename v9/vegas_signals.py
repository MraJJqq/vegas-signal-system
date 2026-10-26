"""VEGAS V9 signal rules: 4H zone observation, later 1H EMA12 confirmation."""
from __future__ import annotations
from typing import Any

LINES = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
ZONES = (("中锋", ("中锋EMA144", "中锋EMA169")), ("红峰", ("红峰EMA576", "红峰EMA676")))
FILTER_PERIOD = 12
HOUR_MS = 3600000


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


def _touched_zones(low: float, high: float, values: dict[str, list[float | None]], index: int) -> list[str]:
    """Return zones whose full EMA band overlaps the candle's [low, high] range."""
    hits: list[str] = []
    for zone_name, labels in ZONES:
        a, b = (values[label][index] for label in labels)
        if a is None or b is None:
            continue
        zone_low, zone_high = min(a, b), max(a, b)
        if low <= zone_high and high >= zone_low:
            hits.extend(label for label in labels)
    return hits


def detect_formal_signals(
    symbol: str,
    candles_1h: list[dict[str, Any]],
    candles_4h: list[dict[str, Any]],
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """A closed 4H candle overlapping a Vegas band starts observation; a strictly later closed 1H candle confirms."""
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

    events: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, candle in enumerate(closed_4h):
        ts = int(candle["timestamp_ms"])
        if ts > last_processed_4h:
            events.append((ts + 4 * HOUR_MS, 0, index, candle))
    for index, candle in enumerate(closed_1h):
        ts = int(candle["timestamp_ms"])
        if ts > last_processed_1h:
            events.append((ts + HOUR_MS, 1, index, candle))
    events.sort(key=lambda event: (event[0], event[1]))

    for close_time_ms, event_type, index, candle in events:
        ts = int(candle["timestamp_ms"])
        if event_type == 0:
            if not observing:
                hits = _touched_zones(
                    float(candle["low"]), float(candle["high"]), values_4h, index
                )
                if hits:
                    observing = True
                    touched_lines = hits
                    touch_timestamp_ms = ts
            last_processed_4h = max(last_processed_4h, ts)
            continue

        fv = filter_values_1h[index]
        touch_close_time = (
            int(touch_timestamp_ms) + 4 * HOUR_MS
            if touch_timestamp_ms is not None else None
        )
        if observing and touch_close_time is not None and close_time_ms > touch_close_time and fv is not None:
            close_price = float(candle["close"])
            side = "上方" if close_price > fv else "下方" if close_price < fv else None
            if side is not None:
                signals.append({
                    "formal_signal": True,
                    "symbol": symbol,
                    "timeframe": "1H",
                    "observation_timeframe": "4H",
                    "phase": "信号期",
                    "line": ", ".join(touched_lines),
                    "touch_timestamp_ms": touch_timestamp_ms,
                    "filter_line": "1H EMA12",
                    "filter_side": side,
                    "filter_value": fv,
                    "close_price": close_price,
                    "candle_timestamp_ms": ts,
                })
                observing, touched_lines, touch_timestamp_ms = False, [], None
        last_processed_1h = max(last_processed_1h, ts)

    state.update({
        "observing": observing,
        "touched_lines": touched_lines,
        "touch_timestamp_ms": touch_timestamp_ms,
        "last_processed_1h_timestamp_ms": last_processed_1h,
        "last_processed_4h_timestamp_ms": last_processed_4h,
    })
    return signals
