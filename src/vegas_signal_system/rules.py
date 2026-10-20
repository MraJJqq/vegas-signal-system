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


def scan_symbol(symbol: dict[str, Any], provider, config: dict[str, Any]) -> SignalObservation:
    """Scan one configured symbol and return a conservative observation.

    A missing timeframe is treated as unavailable, never as a trade signal.
    This baseline does not claim a confirmed entry until detailed signal triggers
    have been formally locked and validated against historical data.
    """
    symbol_id, symbol_name = str(symbol["id"]), str(symbol["name"])
    timeframes = config.get("timeframes", {})
    direction_sources = list(timeframes.get("direction_sources", ["4h", "8h"]))
    entry_timeframes = list(timeframes.get("entry_watch", ["1h", "2h"]))
    period = int(config.get("indicators", {}).get("direction_ema", 144))
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for timeframe in direction_sources + entry_timeframes:
        try:
            raw = provider.load(symbol_id, timeframe)
            frames[timeframe] = add_indicators(raw, config)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"{timeframe}: {exc}")

    timestamp = ""
    for timeframe in direction_sources + entry_timeframes:
        if timeframe in frames and not frames[timeframe].empty:
            timestamp = frames[timeframe].iloc[-1]["timestamp"].isoformat()
            break

    directions = {tf: classify_direction(frames[tf], period) if tf in frames else "unavailable" for tf in direction_sources}
    direction_values = list(directions.values())
    if any(value == "unavailable" for value in direction_values):
        status, message = "DATA_UNAVAILABLE", "缺少方向周期行情；不产生交易信号。"
    elif any(value == "neutral" for value in direction_values):
        status, message = "NO_TRADE_NEUTRAL", "至少一个方向周期不明确；保持观察。"
    elif len(set(direction_values)) > 1:
        status, message = "NO_TRADE_CONFLICT", "4H/8H方向冲突；按规则空仓。"
    else:
        status, message = "DIRECTION_ALIGNED", "方向周期一致；继续检查1H/2H中锋触碰及后续信号条件。"

    entry_timeframe = None
    close = None
    if status == "DIRECTION_ALIGNED":
        for timeframe in entry_timeframes:
            if timeframe in frames and not frames[timeframe].empty:
                entry_timeframe = timeframe
                close = _last_close(frames[timeframe])
                break
        # The scaffold intentionally does not promote direction alignment alone to an entry signal.
        status = "WATCH_ENTRY_CONDITIONS"
        message = "方向一致，但尚未验证完整进场触发条件；仅观察，不视为正式信号。"
    elif errors and status == "DATA_UNAVAILABLE":
        message += " 数据详情：" + " | ".join(errors)

    return SignalObservation(
        symbol_id=symbol_id,
        symbol_name=symbol_name,
        timestamp=timestamp,
        status=status,
        direction_4h=directions.get("4h", "unavailable"),
        direction_8h=directions.get("8h", "unavailable"),
        entry_timeframe=entry_timeframe,
        close=close,
        message=message,
    )
