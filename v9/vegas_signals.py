"""VEGAS V9 signal rules: 4H zone observation, later 2H EMA12 confirmation."""
from __future__ import annotations
from typing import Any

LINES = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
ZONES = (("中锋", ("中锋EMA144", "中锋EMA169")), ("红峰", ("红峰EMA576", "红峰EMA676")))
FILTER_PERIOD = 12
HOUR_MS = 3600000
SIGNAL_GRANULARITY = "2H"
SIGNAL_INTERVAL_MS = 2 * HOUR_MS


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

def _merge_events(
    events_4h: list[tuple[int, int, int, dict[str, Any]]],
    events_2h: list[tuple[int, int, int, dict[str, Any]]],
):
    """Merge already time-ordered candle events in O(n), with 4H winning equal-time ties."""
    i4 = i2 = 0
    while i4 < len(events_4h) and i2 < len(events_2h):
        if events_4h[i4][0] <= events_2h[i2][0]:
            yield events_4h[i4]
            i4 += 1
        else:
            yield events_2h[i2]
            i2 += 1
    yield from events_4h[i4:]
    yield from events_2h[i2:]


def detect_formal_signals(
    symbol: str,
    candles_2h: list[dict[str, Any]],
    candles_4h: list[dict[str, Any]],
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """A closed 4H candle overlapping a Vegas band starts observation; a strictly later closed 2H candle confirms."""
    closed_2h = sorted((c for c in candles_2h if c.get("closed")), key=lambda c: c["timestamp_ms"])
    closed_4h = sorted((c for c in candles_4h if c.get("closed")), key=lambda c: c["timestamp_ms"])
    if not closed_2h or not closed_4h:
        return []
    if state is None:
        state = {}

    observing = bool(state.get("observing", False))
    touched_lines = [str(line) for line in state.get("touched_lines", [])]
    touch_timestamp_ms = state.get("touch_timestamp_ms")
    last_processed_2h = int(state.get("last_processed_2h_timestamp_ms", -1))
    last_processed_4h = int(state.get("last_processed_4h_timestamp_ms", -1))

    closes_4h = [float(c["close"]) for c in closed_4h]
    values_4h = {label: ema(closes_4h, period) for label, period in LINES}
    closes_2h = [float(c["close"]) for c in closed_2h]
    filter_values_2h = ema(closes_2h, FILTER_PERIOD)
    signals: list[dict[str, Any]] = []

    events_4h: list[tuple[int, int, int, dict[str, Any]]] = []
    events_2h: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, candle in enumerate(closed_4h):
        ts = int(candle["timestamp_ms"])
        if ts > last_processed_4h:
            events_4h.append((ts + 4 * HOUR_MS, 0, index, candle))
    for index, candle in enumerate(closed_2h):
        ts = int(candle["timestamp_ms"])
        if ts > last_processed_2h:
            events_2h.append((ts + SIGNAL_INTERVAL_MS, 1, index, candle))

    for close_time_ms, event_type, index, candle in _merge_events(events_4h, events_2h):
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

        fv = filter_values_2h[index]
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
                    "timeframe": SIGNAL_GRANULARITY,
                    "observation_timeframe": "4H",
                    "phase": "信号期",
                    "line": ", ".join(touched_lines),
                    "touch_timestamp_ms": touch_timestamp_ms,
                    "filter_line": "2H EMA12",
                    "filter_side": side,
                    "filter_value": fv,
                    "close_price": close_price,
                    "candle_timestamp_ms": ts,
                })
                observing, touched_lines, touch_timestamp_ms = False, [], None
        last_processed_2h = max(last_processed_2h, ts)

    state.update({
        "observing": observing,
        "touched_lines": touched_lines,
        "touch_timestamp_ms": touch_timestamp_ms,
        "last_processed_2h_timestamp_ms": last_processed_2h,
        "last_processed_4h_timestamp_ms": last_processed_4h,
    })
    return signals
