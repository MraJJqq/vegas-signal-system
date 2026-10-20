from __future__ import annotations

import pandas as pd


REQUIRED_OHLCV = ("timestamp", "open", "high", "low", "close", "volume")


def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_OHLCV if column not in frame.columns]
    if missing:
        raise ValueError(f"OHLCV data missing columns: {', '.join(missing)}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="coerce")
    if result["timestamp"].isna().any():
        raise ValueError("OHLCV data contains invalid timestamps")
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError("OHLCV data contains non-numeric or missing values")
    if (result["high"] < result[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLCV high is lower than open, close, or low")
    if (result["low"] > result[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLCV low is higher than open, close, or high")
    return result.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)


def add_indicators(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Calculate configured indicators using only current/past bars."""
    result = validate_ohlcv(frame)
    settings = config.get("indicators", {})
    sma_period = int(settings.get("filter_sma", 2))
    entry_period = int(settings.get("entry_ema", 36))
    direction_period = int(settings.get("direction_ema", 144))
    alternate_direction_period = int(settings.get("direction_ema_alternative", 169))
    major_period = int(settings.get("major_ema", 576))
    result[f"sma_{sma_period}"] = result["close"].rolling(sma_period, min_periods=sma_period).mean()
    result[f"ema_{entry_period}"] = result["close"].ewm(span=entry_period, adjust=False, min_periods=entry_period).mean()
    result[f"ema_{direction_period}"] = result["close"].ewm(span=direction_period, adjust=False, min_periods=direction_period).mean()
    result[f"ema_{alternate_direction_period}"] = result["close"].ewm(span=alternate_direction_period, adjust=False, min_periods=alternate_direction_period).mean()
    result[f"ema_{major_period}"] = result["close"].ewm(span=major_period, adjust=False, min_periods=major_period).mean()
    return result


def classify_direction(frame: pd.DataFrame, period: int = 144) -> str:
    """Return up/down/neutral from the latest close vs EMA and EMA slope.

    This is an explicit baseline classifier, not a claim that every final Vegas rule
    has been formally confirmed. Insufficient history returns neutral.
    """
    key = f"ema_{period}"
    if len(frame) < 2 or key not in frame.columns:
        return "neutral"
    latest, previous = frame.iloc[-1], frame.iloc[-2]
    if pd.isna(latest[key]) or pd.isna(previous[key]):
        return "neutral"
    if latest["close"] > latest[key] and latest[key] > previous[key]:
        return "up"
    if latest["close"] < latest[key] and latest[key] < previous[key]:
        return "down"
    return "neutral"
