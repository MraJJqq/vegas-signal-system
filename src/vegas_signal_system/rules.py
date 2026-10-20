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


def _observation_started(frame: pd.DataFrame, period: int = 144) -> bool:
    """Observation stays active once any available completed candle touches EMA144."""
    key = f"ema_{period}"
    if frame.empty or key not in frame.columns:
        return False
    ema = frame[key]
    touched = (
        frame["low"].le(ema)
        & frame["high"].ge(ema)
        & ema.notna()
    ).fillna(False)
    return bool(touched.any())


def scan_symbol(symbol: dict[str, Any], provider, config: dict[str, Any]) -> SignalObservation:
    """Apply direction gate, then persistent EMA144 observation and EMA12 close-side signal."""
    symbol_id, symbol_name = str(symbol["id"]), str(symbol["name"])
    timeframes = config.get("timeframes", {})
    direction_sources = list(timeframes.get("direction_sources", ["4h", "8h"]))
    entry_timeframes = list(timeframes.get("entry_watch", ["1h", "2h"]))
    indicators = config.get("indicators", {})
    period = int(indicators.get("direction_ema", 144))
    touch_period = int(config.get("rules", {}).get("entry_midline_ema", 144))
    filter_period = int(config.get("rules", {}).get("entry_filter_ema", 12))
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    for timeframe in direction_sources + entry_timeframes:
        try:
            frame = add_indicators(provider.load(symbol_id, timeframe), config)
            filter_key = f"ema_{filter_period}"
            if filter_key not in frame.columns:
                frame[filter_key] = frame["close"].ewm(
                    span=filter_period, adjust=False, min_periods=filter_period
                ).mean()
            frames[timeframe] = frame
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"{timeframe}: {exc}")

    timestamp = ""
    for timeframe in entry_timeframes + direction_sources:
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
        status, message = "NO_TRADE_CONFLICT", "配置的方向来源方向冲突；按规则空仓。"
    else:
        status, message = "DIRECTION_ALIGNED", "方向周期一致；检查1H/2H持续观察期与过滤线。"

    entry_timeframe = None
    close = None
    if status == "DIRECTION_ALIGNED":
        allowed_direction = direction_values[0]
        available = [tf for tf in entry_timeframes if tf in frames and not frames[tf].empty]
        qualified = []
        for tf in available:
            frame = frames[tf]
            filter_key = f"ema_{filter_period}"
            if not _observation_started(frame, touch_period):
                continue
            latest = frame.iloc[-1]
            if pd.isna(latest.get(filter_key)):
                continue
            if allowed_direction == "up" and float(latest["close"]) > float(latest[filter_key]):
                qualified.append((tf, frame))
            elif allowed_direction == "down" and float(latest["close"]) < float(latest[filter_key]):
                qualified.append((tf, frame))

        if qualified:
            entry_timeframe, selected = qualified[0]
            close = _last_close(selected)
            status = "ENTRY_SIGNAL_LONG" if allowed_direction == "up" else "ENTRY_SIGNAL_SHORT"
            side_text = (
                f"收盘价在EMA{filter_period}上方，做多信号"
                if allowed_direction == "up"
                else f"收盘价在EMA{filter_period}下方，做空信号"
            )
            message = (
                f"{entry_timeframe.upper()}观察期持续有效：历史K线已触碰EMA{touch_period}，"
                f"最新完整K线{side_text}；方向过滤通过。"
            )
        elif not available:
            status = "DATA_UNAVAILABLE"
            message = "方向周期一致，但缺少1H/2H进场观察数据；不产生交易信号。"
        else:
            entry_timeframe = available[0]
            close = _last_close(frames[entry_timeframe])
            status = "WATCH_ENTRY_CONDITIONS"
            message = (
                f"方向周期一致；继续观察。需在持续有效的中锋观察期内，"
                f"最新完整K线收盘价位于EMA{filter_period}对应方向一侧。"
            )
    elif errors and status == "DATA_UNAVAILABLE":
        message += " 数据详情：" + " | ".join(errors)

    return SignalObservation(
        symbol_id=symbol_id, symbol_name=symbol_name, timestamp=timestamp,
        status=status, direction_4h=directions.get("4h", "unavailable"),
        direction_8h=directions.get("8h", "unavailable"),
        entry_timeframe=entry_timeframe, close=close, message=message,
    )
