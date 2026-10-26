"""Independent VEGAS V9 A-share signal engine; no imports from v9/."""
from __future__ import annotations
from typing import Any

LINES = (("中锋EMA144", 144), ("中锋EMA169", 169), ("红峰EMA576", 576), ("红峰EMA676", 676))
TIMEFRAME = "4H"


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        out[i] = prev
    return out


def detect_formal_signals(symbol: str, candles: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Use closed 4H candles for both zone touch and EMA12 confirmation."""
    closed = sorted((c for c in candles if c.get("closed")), key=lambda c: c["timestamp_ms"])
    if not closed:
        return []

    # A 1H state cannot be safely carried into the new 4H rules. Start clean at
    # the latest available closed 4H candle, then process only future candles.
    if state.get("timeframe") != TIMEFRAME:
        state.clear()
        state.update({
            "timeframe": TIMEFRAME,
            "observing": False,
            "touched_lines": [],
            "touch_timestamp_ms": None,
            "last_processed_timestamp_ms": int(closed[-1]["timestamp_ms"]),
        })
        return []

    closes = [float(c["close"]) for c in closed]
    lines = {name: ema(closes, period) for name, period in LINES}
    filt = ema(closes, 12)
    observing = bool(state.get("observing", False))
    touched = list(state.get("touched_lines", []))
    touch = state.get("touch_timestamp_ms")
    last = int(state.get("last_processed_timestamp_ms", -1))
    signals: list[dict[str, Any]] = []

    for i, candle in enumerate(closed):
        ts = int(candle["timestamp_ms"])
        if ts <= last:
            continue
        fv = filt[i]
        high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

        # A formal signal must occur on a later closed 4H candle than the touch.
        if observing and fv is not None:
            side = "上方" if close > fv else "下方" if close < fv else None
            if side:
                signals.append({
                    "formal_signal": True,
                    "symbol": symbol,
                    "timeframe": TIMEFRAME,
                    "line": ", ".join(touched),
                    "touch_timestamp_ms": touch,
                    "filter_line": "EMA12",
                    "filter_side": side,
                    "filter_value": fv,
                    "close_price": close,
                    "candle_timestamp_ms": ts,
                })
                observing, touched, touch = False, [], None
                last = ts
                continue

        if not observing:
            # Treat the whole middle-peak or red-peak band as the trigger zone.
            hits = []
            for name, period in (("中锋", (144, 169)), ("红峰", (576, 676))):
                p1, p2 = period
                e1, e2 = lines[f"{name}EMA{p1}"][i], lines[f"{name}EMA{p2}"][i]
                if e1 is not None and e2 is not None:
                    zone_low, zone_high = min(e1, e2), max(e1, e2)
                    if low <= zone_high and high >= zone_low:
                        hits.append(f"{name}EMA{p1}–EMA{p2}")
            if hits:
                observing, touched, touch = True, hits, ts
        last = ts

    state.update({
        "timeframe": TIMEFRAME,
        "observing": observing,
        "touched_lines": touched,
        "touch_timestamp_ms": touch,
        "last_processed_timestamp_ms": last,
    })
    return signals
