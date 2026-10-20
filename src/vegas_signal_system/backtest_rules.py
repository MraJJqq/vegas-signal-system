from __future__ import annotations

import pandas as pd

from .indicators import validate_ohlcv


def add_backtest_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Add EMA12 filter and EMA144 midline using only current/past candles."""
    result = validate_ohlcv(frame)
    result["ema_12"] = result["close"].ewm(
        span=12, adjust=False, min_periods=12
    ).mean()
    result["ema_144"] = result["close"].ewm(
        span=144, adjust=False, min_periods=144
    ).mean()
    return result


def entry_candidate(frame: pd.DataFrame, direction: str) -> pd.Series:
    """Return a per-candle entry-candidate mask for one timeframe.

    Rules:
    - The candle's high-low range must cover EMA144.
    - For an up direction, the candle must close above EMA12.
    - For a down direction, the candle must close below EMA12.
    - Direction must be explicitly 'up' or 'down'; neutral/unknown yields no signal.
    This identifies a candidate only; it does not simulate fills or exits.
    """
    if direction not in {"up", "down"}:
        return pd.Series(False, index=frame.index, dtype=bool)

    required = {"high", "low", "close", "ema_12", "ema_144"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing indicator columns: {', '.join(sorted(missing))}")

    touched = (
        frame["low"].le(frame["ema_144"])
        & frame["high"].ge(frame["ema_144"])
        & frame["ema_144"].notna()
    )
    if direction == "up":
        filter_side = frame["close"].gt(frame["ema_12"])
    else:
        filter_side = frame["close"].lt(frame["ema_12"])
    return (touched & filter_side & frame["ema_12"].notna()).fillna(False)


def build_entry_candidates(frame: pd.DataFrame, timeframe: str, direction: str) -> pd.DataFrame:
    """Return rows meeting the finalized touch + EMA12 close-side rule."""
    if timeframe.lower() not in {"1h", "2h"}:
        raise ValueError("Entry timeframe must be 1h or 2h")
    result = add_backtest_indicators(frame)
    mask = entry_candidate(result, direction)
    candidates = result.loc[mask].copy()
    candidates["timeframe"] = timeframe.lower()
    candidates["direction"] = direction
    candidates["signal"] = candidates["direction"].map(
        {"up": "LONG_CANDIDATE", "down": "SHORT_CANDIDATE"}
    )
    return candidates
