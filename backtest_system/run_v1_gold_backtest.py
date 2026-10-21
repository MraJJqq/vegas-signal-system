"""V1 automatic GOLD backtest: historical signal recognition + Bitget data + report.

Uses only closed candles. V1 rule evaluator is deliberately separate from V3.
Direction filter: 4H and 8H close relative to their own EMA144 must agree.
Entry setup: 1H/2H candle range touches EMA144; the same closed candle must
close on the agreed direction's EMA12 side. Entry is at that candle close.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bitget_market_data import fetch_history_candles, candles_to_csv_rows
from download_gold_data import fetch_preferred_timeframe
from v1_trading_system import (\n    Candle, Direction, SignalEvent, VegasBacktestV2, prioritize_same_symbol_signals,\n)

HOURS = {"1H": 1, "2H": 2, "4H": 4, "8H": 8}


def ema(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        result[i] = prev
    return result


def candle_close_time(c, timeframe: str) -> datetime:
    return c.timestamp + timedelta(hours=HOURS[timeframe])


def run(symbol: str, days: int, output_dir: Path) -> dict:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    # Fetch native 1H candles once, then prefer native higher timeframes where
    # Bitget supports them. Bitget's v2 history-candles endpoint does not list
    # 2H or 8H granularity, so those series are built only from complete,
    # contiguous closed 1H candles by the shared data-ingestion helper.
    warmup_start = start - timedelta(days=70)
    hourly = fetch_history_candles(symbol=symbol, timeframe="1H", start=warmup_start, end=end)
    if not hourly:
        raise RuntimeError(f"Bitget returned no closed 1H candles for {symbol}")
    data = {"1H": hourly}
    for tf in ("2H", "4H", "8H"):
        candles, _source = fetch_preferred_timeframe(
            symbol=symbol, timeframe=tf, start=warmup_start, end=end, hourly=hourly
        )
        if not candles:
            raise RuntimeError(f"Bitget returned no closed or aggregated candles for {symbol} {tf}")
        data[tf] = candles

    indicators = {}
    for tf, candles in data.items():
        closes = [c.close for c in candles]
        indicators[tf] = {
            "ema12": ema(closes, 12),
            "ema36": ema(closes, 36),
            "ema144": ema(closes, 144),
        }

    # Time-indexed higher-timeframe direction is only available after that candle closes.
    direction_by_tf = {}
    for tf in ("4H", "8H"):
        series = []
        for i, c in enumerate(data[tf]):
            mid = indicators[tf]["ema144"][i]
            if mid is not None:
                side = Direction.LONG if c.close > mid else Direction.SHORT if c.close < mid else None
                if side is not None:
                    series.append((candle_close_time(c, tf), side))
        direction_by_tf[tf] = series

    def last_direction(tf: str, t: datetime):
        found = None
        for close_time, side in direction_by_tf[tf]:
            if close_time <= t:
                found = side
            else:
                break
        return found

    signals = []
    touches = 0
    direction_passes = 0
    for tf in ("1H", "2H"):
        candles = data[tf]
        ind = indicators[tf]
        for i, c in enumerate(candles):
            close_time = candle_close_time(c, tf)
            if close_time < start or close_time > end:
                continue
            mid, filt = ind["ema144"][i], ind["ema12"][i]
            if mid is None or filt is None:
                continue
            # Touch is based on candle range; all decisions occur after candle close.
            if c.low <= mid <= c.high:
                touches += 1
                d4, d8 = last_direction("4H", close_time), last_direction("8H", close_time)
                if d4 is None or d8 is None or d4 != d8:
                    continue
                direction_passes += 1
                if d4 is Direction.LONG and c.close > filt:
                    signals.append(SignalEvent(symbol.upper(), tf, close_time, Direction.LONG, c.close))
                elif d4 is Direction.SHORT and c.close < filt:
                    signals.append(SignalEvent(symbol.upper(), tf, close_time, Direction.SHORT, c.close))

    # Count signals after the confirmed same-symbol/same-timeframe-priority rule.
    signals.sort(key=lambda s: (s.timestamp, s.timeframe))
    prioritized_signals = prioritize_same_symbol_signals(signals)
    engine = VegasBacktestV2()
    for tf, candles in data.items():
        engine.record_candles([
            Candle(symbol=c.symbol, timeframe=tf, timestamp=c.timestamp, open=c.open,
                   high=c.high, low=c.low, close=c.close, is_closed=True,
                   is_synthetic=c.is_synthetic)
            for c in candles if start - timedelta(days=70) <= c.timestamp < end
        ])
    # Recognize the explicitly defined bullish 1H reversal pattern using closed closes.
    reversal_events = []
    hourly_candles = data["1H"]
    hourly_closes = [c.close for c in hourly_candles]
    reversal_indices = bullish_reversal_indices(
        hourly_closes, indicators["1H"]["ema36"], indicators["1H"]["ema144"]
    )
    for index in reversal_indices:
        candle = hourly_candles[index]
        event_time = candle_close_time(candle, "1H")
        if start <= event_time <= end:
            reversal_events.append((event_time, candle.close, candle.is_synthetic))

    # Replay signals and confirmed reversal events chronologically, never using an open candle.
    signals_by_time = {}
    for signal in prioritized_signals:
        signals_by_time.setdefault(signal.timestamp, []).append(signal)
    reversals_by_time = {}
    for event_time, price, synthetic in reversal_events:
        reversals_by_time.setdefault(event_time, []).append((price, synthetic))

    for event_time in sorted(set(signals_by_time) | set(reversals_by_time)):
        if event_time in signals_by_time:
            engine.process_signals(signals_by_time[event_time])
        if event_time in reversals_by_time:
            for price, synthetic in reversals_by_time[event_time]:
                has_short_exposure = any(
                    p.symbol == symbol.upper() and p.is_open
                    and p.kind in {"main", "addon"} and p.direction is Direction.SHORT
                    for p in engine.report.positions
                )
                if has_short_exposure:
                    engine.confirm_reversal(
                        symbol=symbol.upper(),
                        opposite_direction=Direction.LONG,
                        timestamp=event_time,
                        price=price,
                        timeframe="1H",
                        reversal_structure_confirmed=True,
                        synthetic_source=synthetic,
                    )

    output_dir.mkdir(parents=True, exist_ok=True)
    all_candles = [c for tf in data for c in data[tf] if start <= c.timestamp < end]
    rows = candles_to_csv_rows(sorted(all_candles, key=lambda c: (c.timeframe, c.timestamp)))
    with (output_dir / "gold_candles.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    report = engine.results()
    report["market_data"] = {
        "provider": "Bitget USDT-FUTURES",
        "symbol": symbol.upper(),
        "requested_days": days,
        "range_start_utc": start.isoformat(),
        "range_end_utc": end.isoformat(),
        "candles_by_timeframe_including_warmup": {tf: len(cs) for tf, cs in data.items()},
        "candles_exported_target_window": len(all_candles),
        "ema144_touch_candidates": touches,
        "direction_alignment_passes": direction_passes,
        "recognized_signals_before_priority": len(signals),
        "signals_after_same_symbol_time_priority": len(prioritized_signals),
        "signals_removed_by_same_symbol_time_priority": len(signals) - len(prioritized_signals),\n        "confirmed_bullish_reversal_patterns": len(reversal_events),
        "positions_opened": report["summary"]["positions_opened"],
        "positions_closed": report["summary"]["positions_closed"],
        "entry_rule": "4H/8H close-vs-EMA144 directions agree; 1H/2H range touches EMA144; same closed candle closes on agreed side of EMA12",
        "limitations": [
            "Direction is operationalized as close relative to EMA144 because the prior V1 notes do not define a separate direction formula in the codebase.",
            "Liquidation events are not inferred from OHLC because leverage and liquidation prices are not specified; positions remain open unless liquidation is verified.",
            "No fees, slippage, funding, account return, or unrealized PnL are calculated."
        ]
    }
    (output_dir / "gold_backtest_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XAUUSDT")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--output-dir", type=Path, default=Path("output"))
    a = p.parse_args()
    if not 30 <= a.days <= 730:
        p.error("--days must be between 30 and 730")
    try:
        report = run(a.symbol, a.days, a.output_dir)
    except Exception as exc:
        print(f"V1 GOLD backtest failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"summary": report["summary"], "market_data": report["market_data"],
                      "report_file": str(a.output_dir / "gold_backtest_report.json"),
                      "candles_file": str(a.output_dir / "gold_candles.csv")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
