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


def entry_observation(frame: pd.DataFrame) -> pd.DataFrame:
    """Track the EMA144-touch observation phase and EMA12 close-side state.

    OHLC data can only approximate an intrabar contact: low <= EMA144 <= high.
    Once a completed candle registers that contact, observation remains active
    for subsequent candles in this supplied chronological series. A later candle
    can therefore qualify by closing on the relevant side of EMA12 even if that
    later candle does not itself touch EMA144.

    The observation phase intentionally has no reset rule yet; one must be agreed
    separately rather than silently invented here.
    """
    required = {"high", "low", "close", "ema_12", "ema_144"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing indicator columns: {', '.join(sorted(missing))}")

    result = frame.copy()
    touch_now = (
        result["low"].le(result["ema_144"])
        & result["high"].ge(result["ema_144"])
        & result["ema_144"].notna()
    ).fillna(False)
    result["ema144_touch_now"] = touch_now
    result["observation_active"] = touch_now.cummax().astype(bool)
    result["ema12_above"] = (
        result["close"].gt(result["ema_12"]) & result["ema_12"].notna()
    ).fillna(False)
    result["ema12_below"] = (
        result["close"].lt(result["ema_12"]) & result["ema_12"].notna()
    ).fillna(False)
    return result


def entry_candidate(frame: pd.DataFrame, direction: str) -> pd.Series:
    """Mark candidate candles during observation when close is on EMA12's side.

    Up: after EMA144 has been touched, close above EMA12.
    Down: after EMA144 has been touched, close below EMA12.
    Neutral/unknown direction yields no candidate. EMA144 need not be touched
    again on the candidate candle.
    """
    if direction not in {"up", "down"}:
        return pd.Series(False, index=frame.index, dtype=bool)

    required = {"high", "low", "close", "ema_12", "ema_144"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing indicator columns: {', '.join(sorted(missing))}")

    observed = entry_observation(frame)
    if direction == "up":
        filter_side = observed["ema12_above"]
    else:
        filter_side = observed["ema12_below"]
    return (observed["observation_active"] & filter_side).fillna(False)


def build_entry_candidates(frame: pd.DataFrame, timeframe: str, direction: str) -> pd.DataFrame:
    """Return candidate candles after an EMA144 touch and EMA12 close-side check."""
    if timeframe.lower() not in {"1h", "2h"}:
        raise ValueError("Entry timeframe must be 1h or 2h")
    result = add_backtest_indicators(frame)
    observed = entry_observation(result)
    mask = entry_candidate(result, direction)
    candidates = observed.loc[mask].copy()
    candidates["timeframe"] = timeframe.lower()
    candidates["direction"] = direction
    candidates["signal"] = candidates["direction"].map(
        {"up": "LONG_CANDIDATE", "down": "SHORT_CANDIDATE"}
    )
    return candidates
