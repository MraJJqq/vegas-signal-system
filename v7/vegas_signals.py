"""V7 formal signal rule: touching 中锋/红峰 immediately emits a formal signal."""
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
    """A closed 4H candle touching 中锋/红峰 immediately emits a formal signal.
    EMA12/filter-side confirmation is intentionally not used.
    """
    closed = sorted((c for c in candles if c.get("closed")), key=lambda c: c["timestamp_ms"])
    if not closed:
        return []
    closes = [float(c["close"]) for c in closed]
    lines = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
    line_values = {label: ema(closes, period) for label, period in lines}
    signals: list[dict[str, Any]] = []
    for index, candle in enumerate(closed):
        high, low = float(candle["high"]), float(candle["low"])
        for label, _period in lines:
            line_value = line_values[label][index]
            if line_value is None or not (low <= line_value <= high):
                continue
            signals.append({
                "symbol": symbol,
                "timeframe": "4H",
                "signal_type": "FORMAL_SIGNAL",
                "direction": "OBSERVATION",
                "trigger": "price_touched_vegas_line",
                "line": label,
                "line_value": line_value,
                "close": float(candle["close"]),
                "candle_timestamp_ms": candle["timestamp_ms"],
            })
    return signals
