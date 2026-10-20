from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import akshare as ak
import pandas as pd

from vegas_signal_system.data import resample_ohlcv
from vegas_signal_system.indicators import add_indicators, classify_direction
from vegas_signal_system.rules import _last_close, _last_candle_touches_ema


# Small representative test pool; codes are mainland China exchange symbols.
SYMBOLS = [
    {"id": "ZIJIN_MINING", "name": "紫金矿业", "code": "601899"},
    {"id": "SHANDONG_GOLD", "name": "山东黄金", "code": "600547"},
    {"id": "CHINA_OILFIELD", "name": "中国海油", "code": "600938"},
    {"id": "PETROCHINA", "name": "中国石油", "code": "601857"},
    {"id": "SINOPEC", "name": "中国石化", "code": "600028"},
    {"id": "SMIC", "name": "中芯国际", "code": "688981"},
    {"id": "CAMBRICON", "name": "寒武纪", "code": "688256"},
    {"id": "CSI300_ETF", "name": "沪深300ETF", "code": "510300"},
]

CONFIG = {
    "timeframes": {"direction_sources": ["4h"], "entry_watch": ["1h", "2h"]},
    "indicators": {
        "filter_sma": 2, "entry_ema": 36, "direction_ema": 144,
        "direction_ema_alternative": 169, "major_ema": 576,
    },
    "rules": {"entry_midline_ema": 144},
}


class AkShareAShareProvider:
    """A-share hourly bars from Eastmoney via AkShare; never calls Bitget."""

    def __init__(self):
        self.cache: dict[str, pd.DataFrame] = {}

    def _hourly(self, symbol_id: str) -> pd.DataFrame:
        if symbol_id in self.cache:
            return self.cache[symbol_id]
        item = next((x for x in SYMBOLS if x["id"] == symbol_id), None)
        if item is None:
            raise ValueError(f"Unknown A-share symbol: {symbol_id}")
        raw = ak.stock_zh_a_hist_min_em(
            symbol=item["code"], period="60", adjust=""
        )
        if raw is None or raw.empty:
            raise ValueError(f"Eastmoney/AkShare returned no 60-minute bars for {item['code']}")
        # AkShare's Chinese column labels are stable in the documented interface.
        column_map = {
            "时间": "timestamp", "日期": "timestamp",
            "开盘": "open", "最高": "high", "最低": "low",
            "收盘": "close", "成交量": "volume",
        }
        raw = raw.rename(columns=column_map)
        missing = [c for c in ("timestamp", "open", "high", "low", "close", "volume") if c not in raw.columns]
        if missing:
            raise ValueError(f"Unexpected AkShare columns for {item['code']}: missing {missing}")
        frame = raw[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        # A-share timestamps are China local time. Convert to UTC for the shared indicator engine.
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        if frame["timestamp"].dt.tz is None:
            frame["timestamp"] = frame["timestamp"].dt.tz_localize("Asia/Shanghai").dt.tz_convert("UTC")
        else:
            frame["timestamp"] = frame["timestamp"].dt.tz_convert("UTC")
        for col in ("open", "high", "low", "close", "volume"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna().sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        if len(frame) < 300:
            raise ValueError(f"Only {len(frame)} hourly bars returned; insufficient for EMA144 direction checks")
        self.cache[symbol_id] = frame
        return frame

    def load(self, symbol_id: str, timeframe: str) -> pd.DataFrame:
        hourly = self._hourly(symbol_id)
        return resample_ohlcv(hourly, timeframe)


def main() -> None:
    provider = AkShareAShareProvider()
    rows = []
    for item in SYMBOLS:
        try:
            direction_frame = add_indicators(provider.load(item["id"], "4h"), CONFIG)
            one_hour = add_indicators(provider.load(item["id"], "1h"), CONFIG)
            two_hour = add_indicators(provider.load(item["id"], "2h"), CONFIG)
            direction = classify_direction(direction_frame, 144)
            latest = one_hour.iloc[-1]
            touched_tf = None
            if _last_candle_touches_ema(two_hour, 144):
                touched_tf = "2h"
            elif _last_candle_touches_ema(one_hour, 144):
                touched_tf = "1h"
            if direction == "neutral":
                status = "NO_TRADE_NEUTRAL"
                message = "4H方向不明确，保持观察。"
            elif touched_tf:
                status = "WATCH_ENTRY_CONFIRMATION"
                message = f"4H方向={direction}；{touched_tf.upper()}最新完整K线触碰EMA144，仅为观察候选，不是正式进场信号。"
            else:
                status = "WATCH_ENTRY_CONDITIONS"
                message = f"4H方向={direction}；1H/2H最新完整K线未触碰EMA144，继续观察。"
            rows.append({
                "symbol_id": item["id"], "symbol_name": item["name"], "code": item["code"],
                "timestamp": latest["timestamp"].isoformat(), "close": float(latest["close"]),
                "direction_4h": direction, "status": status, "entry_timeframe": touched_tf,
                "message": message, "hourly_bars": len(provider._hourly(item["id"])),
                "data_source": "Eastmoney via AkShare",
            })
        except Exception as exc:
            rows.append({
                "symbol_id": item["id"], "symbol_name": item["name"], "code": item["code"],
                "timestamp": "", "close": None, "direction_4h": "unavailable",
                "status": "DATA_UNAVAILABLE", "entry_timeframe": None,
                "message": f"{type(exc).__name__}: {exc}", "data_source": "Eastmoney via AkShare",
            })
    result = pd.DataFrame(rows)
    out = Path("output/ashare")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result.to_csv(out / f"ashare_scan_{stamp}.csv", index=False, encoding="utf-8-sig")
    result.to_json(out / f"ashare_scan_{stamp}.json", orient="records", force_ascii=False, indent=2)
    print(result.to_string(index=False))
    print("\nA-share scan complete. Observation only; no orders were placed.")


if __name__ == "__main__":
    main()
