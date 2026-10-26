"""Independent VEGAS V9 A-share signal engine using native 1H candles."""
from __future__ import annotations
from typing import Any

TIMEFRAME = "1H"
EMA_PERIODS = (12, 144, 169, 576, 676)

def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    value = sum(values[:period]) / period
    out[period - 1] = value
    alpha = 2.0 / (period + 1)
    for i in range(period, len(values)):
        value = alpha * values[i] + (1.0 - alpha) * value
        out[i] = value
    return out

def detect_formal_signals(symbol: str, candles: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Zone touch starts observation; a later closed candle vs EMA12 confirms."""
    closed = sorted((c for c in candles if c.get("closed")), key=lambda c: int(c["timestamp_ms"]))
    if len(closed) < 676:
        raise ValueError(f"Need at least 676 closed native 1H candles; got {len(closed)}")
    if state.get("timeframe") != TIMEFRAME:
        state.clear()
        state.update({"timeframe": TIMEFRAME, "observing": False, "touched_lines": [],
                      "touch_timestamp_ms": None,
                      "last_processed_timestamp_ms": int(closed[-2]["timestamp_ms"])})
    closes = [float(c["close"]) for c in closed]
    values = {p: ema(closes, p) for p in EMA_PERIODS}
    observing = bool(state.get("observing", False))
    touched = list(state.get("touched_lines", []))
    touch_ts = state.get("touch_timestamp_ms")
    last_ts = int(state.get("last_processed_timestamp_ms", -1))
    signals = []
    for i, candle in enumerate(closed):
        ts = int(candle["timestamp_ms"])
        if ts <= last_ts:
            continue
        high, low, close = (float(candle[k]) for k in ("high", "low", "close"))
        fv = values[12][i]
        if observing and ts > int(touch_ts or 0) and fv is not None:
            side = "上方" if close > fv else "下方" if close < fv else None
            if side:
                signals.append({"formal_signal": True, "symbol": symbol, "timeframe": TIMEFRAME,
                    "line": ", ".join(touched), "touch_timestamp_ms": touch_ts,
                    "filter_line": "EMA12", "filter_side": side, "filter_value": fv,
                    "close_price": close, "candle_timestamp_ms": ts})
                observing, touched, touch_ts = False, [], None
                last_ts = ts
                continue
        if not observing:
            hits = []
            for label, p1, p2 in (("中锋", 144, 169), ("红峰", 576, 676)):
                e1, e2 = values[p1][i], values[p2][i]
                if e1 is None or e2 is None:
                    continue
                band_low, band_high = min(e1, e2), max(e1, e2)
                if low <= band_high and high >= band_low:
                    hits.append(f"{label}EMA{p1}–EMA{p2}")
            if hits:
                observing, touched, touch_ts = True, hits, ts
        last_ts = ts
    state.update({"timeframe": TIMEFRAME, "observing": observing, "touched_lines": touched,
                  "touch_timestamp_ms": touch_ts, "last_processed_timestamp_ms": last_ts})
    return signals
