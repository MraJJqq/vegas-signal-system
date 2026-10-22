"""V7 formal signal rules: touch 中锋/红峰, then close on one side of EMA12."""
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
    """After a closed candle touches 中锋 or 红峰, keep observing subsequent
    closed candles; emit a formal signal when a close is above/below EMA12.
    Only the available 4H candle series is used. No timeout is imposed here.
    """
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
    # Each touch starts an observation window. A qualifying close on this candle
    # or any later closed candle in the supplied history produces a signal.
    # Historical signals are deduplicated by (candle timestamp, touched line).
    emitted: set[tuple[int, str]] = set()
    touched_lines: set[str] = set()

    for index, candle in enumerate(closed):
        high, low = float(candle["high"]), float(candle["low"])
        for label, _period in lines:
            value = line_values[label][index]
            if value is not None and low <= value <= high:
                touched_lines.add(label)

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

        for label in sorted(touched_lines):
            key = (int(candle["timestamp_ms"]), label)
            if key in emitted:
                continue
            line_value = line_values[label][index]
            # A touch can occur before the current candle; report the current
            # line value only when it exists at this candle.
            if line_value is None:
                continue
            signals.append({
                "symbol": symbol,
                "timeframe": "4H",
                "direction": direction,
                "trigger": "price_touched_vegas_line_then_close_on_ema12_side",
                "line": label,
                "line_value": line_value,
                "filter": "EMA12",
                "filter_value": filter_value,
                "close": close,
                "candle_timestamp_ms": candle["timestamp_ms"],
            })
            emitted.add(key)
    return signals
