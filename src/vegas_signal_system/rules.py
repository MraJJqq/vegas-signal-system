from __future__ import annotations

from typing import Any
import pandas as pd
from .indicators import add_indicators, classify_direction
from .models import SignalObservation


def _last_close(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    value = frame.iloc[-1]["close"]
    return None if pd.isna(value) else float(value)


def _last_candle_touches_ema(frame: pd.DataFrame, period: int = 144) -> bool:
    """True when the latest candle's high-low range covers its EMA line."""
    key = f"ema_{period}"
    if frame.empty or key not in frame.columns:
        return False
    candle = frame.iloc[-1]
    ema = candle[key]
    if pd.isna(ema):
        return False
    return float(candle["low"]) <= float(ema) <= float(candle["high"])


def scan_symbol(symbol: dict[str, Any], provider, config: dict[str, Any]) -> SignalObservation:
    """Scan one symbol conservatively; EMA touch is an observation, not an entry."""
    symbol_id, symbol_name = str(symbol["id"]), str(symbol["name"])
    timeframes = config.get("timeframes", {})
    direction_sources = list(timeframes.get("direction_sources", ["4h", "8h"]))
    entry_timeframes = list(timeframes.get("entry_watch", ["1h", "2h"]))
    indicators = config.get("indicators", {})
    period = int(indicators.get("direction_ema", 144))
    touch_period = int(config.get("rules", {}).get("entry_midline_ema", 144))
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for timeframe in direction_sources + entry_timeframes:
        try:
            frames[timeframe] = add_indicators(provider.load(symbol_id, timeframe), config)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"{timeframe}: {exc}")

    timestamp = ""
    for timeframe in direction_sources + entry_timeframes:
        if timeframe in frames and not frames[timeframe].empty:
            timestamp = frames[timeframe].iloc[-1]["timestamp"].isoformat()
            break

    directions = {
        tf: classify_direction(frames[tf], period) if tf in frames else "unavailable"
        for tf in direction_sources
    }
    direction_values = list(directions.values())
    if any(value == "unavailable" for value in direction_values):
        status, message = "DATA_UNAVAILABLE", "缺少方向周期行情；不产生交易信号。"
    elif any(value == "neutral" for value in direction_values):
        status, message = "NO_TRADE_NEUTRAL", "至少一个方向周期不明确；保持观察。"
    elif len(set(direction_values)) > 1:
        status, message = "NO_TRADE_CONFLICT", "4H/8H方向冲突；按规则空仓。"
    else:
        status, message = "DIRECTION_ALIGNED", "方向周期一致；检查1H/2H的EMA触碰。"

    entry_timeframe = None
    close = None
    if status == "DIRECTION_ALIGNED":
        available = [tf for tf in entry_timeframes if tf in frames and not frames[tf].empty]
        if not available:
            status = "DATA_UNAVAILABLE"
            message = "方向周期一致，但缺少1H/2H进场观察数据；不产生交易信号。"
        else:
            entry_timeframe = available[0]
            close = _last_close(frames[entry_timeframe])
            touched = next((tf for tf in available if _last_candle_touches_ema(frames[tf], touch_period)), None)
            if touched is not None:
                entry_timeframe = touched
                close = _last_close(frames[touched])
                status = "WATCH_ENTRY_CONFIRMATION"
                message = (
                    f"4H/8H方向一致；{touched.upper()}最新完整K线的最高价/最低价覆盖"
                    f"EMA{touch_period}，已记录中锋触碰观察；后续信号确认规则尚未完成，"
                    "不视为正式进场信号。"
                )
            else:
                status = "WATCH_ENTRY_CONDITIONS"
                message = (
                    f"4H/8H方向一致；当前1H/2H最新完整K线未触碰EMA{touch_period}，"
                    "继续观察；不视为正式进场信号。"
                )
    elif errors and status == "DATA_UNAVAILABLE":
        message += " 数据详情：" + " | ".join(errors)

    return SignalObservation(
        symbol_id=symbol_id, symbol_name=symbol_name, timestamp=timestamp,
        status=status, direction_4h=directions.get("4h", "unavailable"),
        direction_8h=directions.get("8h", "unavailable"),
        entry_timeframe=entry_timeframe, close=close, message=message,
    )
