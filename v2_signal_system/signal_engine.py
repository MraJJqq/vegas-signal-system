"""Vegas Signal System V2: signal reminders only; no order execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class Signal:
    timestamp: pd.Timestamp
    direction: str
    retest_line: str
    close: float
    ema12: float
    reason: str


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def generate_signals(
    bars_4h: pd.DataFrame,
    bars_8h: pd.DataFrame,
    *,
    filter_ema: int = 12,
    pioneer_ema: int = 36,
    middle_ema: int = 144,
    red_peak_ema: int = 576,
) -> list[Signal]:
    """Return formal signals from completed OHLC bars.

    Inputs must be chronologically indexed by candle close time and contain
    open/high/low/close columns. The 8H pioneer EMA is forward-filled onto 4H
    timestamps only after an 8H candle has closed (no look-ahead).
    """
    required = {"open", "high", "low", "close"}
    for label, frame in (("4H", bars_4h), ("8H", bars_8h)):
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise TypeError(f"{label} index must be a DatetimeIndex")
        if not required.issubset(frame.columns):
            raise ValueError(f"{label} data must contain {sorted(required)}")
        if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
            raise ValueError(f"{label} index must be unique and chronological")

    if bars_4h.empty or bars_8h.empty:
        return []

    four = bars_4h.copy()
    eight = bars_8h.copy()
    four["ema12"] = _ema(four["close"], filter_ema)
    four["middle"] = _ema(four["close"], middle_ema)
    four["red_peak"] = _ema(four["close"], red_peak_ema)
    eight["pioneer"] = _ema(eight["close"], pioneer_ema)

    # Align only values from 8H candles already closed at each 4H candle close.
    aligned = pd.merge_asof(
        four[["open", "high", "low", "close", "ema12", "middle", "red_peak"]]
        .reset_index(names="timestamp").sort_values("timestamp"),
        eight[["pioneer"]].reset_index(names="timestamp").sort_values("timestamp"),
        on="timestamp",
        direction="backward",
        allow_exact_matches=True,
    ).set_index("timestamp")

    signals: list[Signal] = []
    direction: Optional[str] = None
    waiting_for_retest = False

    previous_middle = None
    previous_red_peak = None
    for ts, row in aligned.iterrows():
        middle = row["middle"]
        red_peak = row["red_peak"]
        if pd.isna(middle) or pd.isna(red_peak) or pd.isna(row["ema12"]):
            previous_middle, previous_red_peak = middle, red_peak
            continue

        # A completed 4H candle must confirm the crossover.
        crossed_up = (
            previous_middle is not None and previous_red_peak is not None
            and pd.notna(previous_middle) and pd.notna(previous_red_peak)
            and previous_middle <= previous_red_peak and middle > red_peak
        )
        crossed_down = (
            previous_middle is not None and previous_red_peak is not None
            and pd.notna(previous_middle) and pd.notna(previous_red_peak)
            and previous_middle >= previous_red_peak and middle < red_peak
        )

        if crossed_up or crossed_down:
            direction = "bullish" if crossed_up else "bearish"
            waiting_for_retest = True
            previous_middle, previous_red_peak = middle, red_peak
            continue  # The crossover candle itself is not the post-cross retest.

        if waiting_for_retest and direction:
            retest_line = None
            # Both levels are evaluated on the same completed 4H candle.
            # If both are touched, choose the line closest to the candle close.
            candidates = []
            for name, level in (("4h_middle", middle), ("8h_pioneer", row["pioneer"])):
                if pd.notna(level) and row["low"] <= level <= row["high"]:
                    candidates.append((name, float(level)))
            if candidates:
                retest_line, _ = min(candidates, key=lambda item: abs(float(row["close"]) - item[1]))
                passed = row["close"] > row["ema12"] if direction == "bullish" else row["close"] < row["ema12"]
                # First retest is final: pass => formal signal; fail => invalidate this setup.
                if passed:
                    signals.append(Signal(
                        timestamp=ts,
                        direction=direction,
                        retest_line=retest_line,
                        close=float(row["close"]),
                        ema12=float(row["ema12"]),
                        reason=f"{direction} 4H middle/red-peak crossover; first retest of {retest_line}; close confirmed against EMA{filter_ema}",
                    ))
                waiting_for_retest = False
                direction = None

        previous_middle, previous_red_peak = middle, red_peak

    return signals
