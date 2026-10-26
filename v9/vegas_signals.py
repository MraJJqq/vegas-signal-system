"""VEGAS V9 signal rules: 4H observation, 1H EMA12 confirmation."""
from __future__ import annotations
from typing import Any

LINES = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
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


def detect_formal_signals(
    symbol: str,
    candles_1h: list[dict[str, Any]],
    candles_4h: list[dict[str, Any]],
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """A closed 4H touch starts observation; a later closed 1H candle vs 1H EMA12 confirms once."""
    closed_1h = sorted(
        (c for c in candles_1h if c.get("closed")), key=lambda c: c["timestamp_ms"]
    )
    closed_4h = sorted(
        (c for c in candles_4h if c.get("closed")), key=lambda c: c["timestamp_ms"]
    )
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

    # Process candle-close events in chronological order. A 4H candle is not
    # known to have touched until its close; a 1H confirmation must close later.
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
                high, low = float(candle["high"]), float(candle["low"])
                hits = [
                    label for label, _period in LINES
                    if values_4h[label][index] is not None
                    and low <= values_4h[label][index] <= high
                ]
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
