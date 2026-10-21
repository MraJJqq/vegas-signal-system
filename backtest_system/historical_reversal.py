"""Closed-candle recognition for the explicitly defined V1 bullish reversal pattern.

Pattern: close above 1H EMA144; later close at/below EMA144 while remaining
above EMA36; later close back above EMA144. All comparisons use candle closes.
"""
from __future__ import annotations


def bullish_reversal_indices(
    closes: list[float],
    ema36: list[float | None],
    ema144: list[float | None],
) -> list[int]:
    """Return indices where the third step (re-close above EMA144) confirms."""
    if not (len(closes) == len(ema36) == len(ema144)):
        raise ValueError("Close and EMA series must have equal lengths.")

    state = 0  # 0: wait above EMA144; 1: wait pullback; 2: wait re-stand
    confirmed: list[int] = []
    for i, close in enumerate(closes):
        pioneer, middle = ema36[i], ema144[i]
        if pioneer is None or middle is None:
            continue

        if state == 0:
            if close > middle:
                state = 1
        elif state == 1:
            if close < pioneer:
                state = 0
            elif close <= middle and close >= pioneer:
                state = 2
        else:  # state == 2
            if close < pioneer:
                state = 0
            elif close > middle:
                confirmed.append(i)
                # The confirmation close can be the start of a later pattern.
                state = 1
    return confirmed
