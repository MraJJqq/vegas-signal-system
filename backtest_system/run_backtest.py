"""V1 end-to-end historical runner.

This runner consumes pre-confirmed Vegas signals; it deliberately does not
invent a signal detector. Each signal must match the close of a downloaded,
closed Bitget candle for the same symbol/timeframe.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bitget_market_data import HistoricalCandle, candles_to_csv_rows, fetch_history_candles
from v1_trading_system import Candle, Direction, SignalEvent, VegasBacktestV2

TIMEFRAME_HOURS = {"1H": 1, "2H": 2, "4H": 4, "8H": 8}


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Datetime must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def load_signals(path: Path) -> list[SignalEvent]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Signals JSON must be a list of confirmed signal objects.")
    signals = []
    for index, item in enumerate(raw):
        try:
            signals.append(SignalEvent(
                symbol=str(item["symbol"]).upper(),
                timeframe=str(item["timeframe"]).upper(),
                timestamp=parse_datetime(str(item["timestamp"])),
                direction=Direction(str(item["direction"]).upper()),
                signal_close=float(item["signal_close"]),
                valid=bool(item.get("valid", True)),
                is_synthetic_source=bool(item.get("is_synthetic_source", False)),
            ))
            signals[-1].validate()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid signal at index {index}: {exc}") from exc
    return signals


def fetch_timeframe_candles(symbol: str, timeframe: str, start: datetime, end: datetime) -> list[HistoricalCandle]:
    """Fetch supported Bitget bars directly; aggregate 2H/8H from complete 1H bars."""
    if timeframe in {"1H", "4H"}:
        return fetch_history_candles(symbol=symbol, timeframe=timeframe, start=start, end=end)
    hours = TIMEFRAME_HOURS[timeframe]
    hourly = fetch_history_candles(symbol=symbol, timeframe="1H", start=start, end=end)
    buckets: dict[datetime, list[HistoricalCandle]] = {}
    for candle in hourly:
        epoch_hour = int(candle.timestamp.timestamp() // 3600)
        bucket_epoch = (epoch_hour // hours) * hours
        bucket_start = datetime.fromtimestamp(bucket_epoch * 3600, tz=timezone.utc)
        buckets.setdefault(bucket_start, []).append(candle)

    aggregated = []
    for bucket_start, bars in sorted(buckets.items()):
        bars.sort(key=lambda bar: bar.timestamp)
        # Never manufacture a higher-timeframe candle from missing hourly data.
        if len(bars) != hours:
            continue
        expected = [bucket_start + timedelta(hours=i) for i in range(hours)]
        if [bar.timestamp for bar in bars] != expected:
            continue
        aggregated.append(HistoricalCandle(
            symbol=symbol.upper(),
            timeframe=timeframe,
            timestamp=bucket_start,
            open=bars[0].open,
            high=max(bar.high for bar in bars),
            low=min(bar.low for bar in bars),
            close=bars[-1].close,
            base_volume=sum(bar.base_volume for bar in bars),
            quote_volume=sum(bar.quote_volume for bar in bars),
        ))
    return [c for c in aggregated if start <= c.timestamp + timedelta(hours=hours) <= end]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(start: datetime, end: datetime, signals_path: Path, output_dir: Path) -> dict:
    if start >= end:
        raise ValueError("--start must be earlier than --end")
    signals = load_signals(signals_path)
    if not signals:
        raise ValueError("Signals file is empty; refusing to produce a misleading backtest.")

    grouped: dict[tuple[str, str], list[SignalEvent]] = {}
    for signal in signals:
        if signal.timeframe not in TIMEFRAME_HOURS:
            raise ValueError(f"Unsupported V1 signal timeframe: {signal.timeframe}")
        if not start <= signal.timestamp <= end:
            raise ValueError(f"Signal timestamp outside requested range: {signal.timestamp}")
        grouped.setdefault((signal.symbol, signal.timeframe), []).append(signal)

    market_by_series = {}
    all_candles = []
    for (symbol, timeframe), series_signals in sorted(grouped.items()):
        # Candle timestamps are opening times; include the candle before the
        # first signal so its close can be matched without looking ahead.
        fetch_start = min(s.timestamp for s in series_signals) - timedelta(hours=TIMEFRAME_HOURS[timeframe])
        fetched = fetch_timeframe_candles(
            symbol=symbol, timeframe=timeframe, start=fetch_start, end=end,
        )
        if not fetched:
            raise RuntimeError(f"Bitget returned no closed candles for {symbol} {timeframe}.")
        market_by_series[(symbol, timeframe)] = {
            candle.timestamp + timedelta(hours=TIMEFRAME_HOURS[timeframe]): candle
            for candle in fetched
        }
        all_candles.extend(fetched)

    # Prevent future-data and price-mismatch errors: every signal must point to
    # the matching closed candle and use its actual close price.
    for signal in signals:
        matched = market_by_series[(signal.symbol, signal.timeframe)].get(signal.timestamp)
        if matched is None:
            raise ValueError(
                f"No matching closed Bitget candle for {signal.symbol} {signal.timeframe} "
                f"at signal close {signal.timestamp.isoformat()}."
            )
        tolerance = max(1e-8, abs(matched.close) * 1e-8)
        if abs(signal.signal_close - matched.close) > tolerance:
            raise ValueError(
                f"Signal close mismatch for {signal.symbol} {signal.timeframe} "
                f"at {signal.timestamp.isoformat()}: signal={signal.signal_close}, "
                f"Bitget close={matched.close}."
            )

    engine = VegasBacktestV2()
    engine.record_candles([
        Candle(
            symbol=c.symbol,
            timeframe=c.timeframe,
            timestamp=c.timestamp,
            open=c.open, high=c.high, low=c.low, close=c.close,
            is_closed=True, is_synthetic=c.is_synthetic,
        )
        for c in all_candles
    ])
    # Submit the complete signal batch so higher-timeframe priority can be
    # applied when several timeframes signal the same symbol at one timestamp.
    engine.process_signals(sorted(signals, key=lambda s: (s.timestamp, s.symbol)))

    output_dir.mkdir(parents=True, exist_ok=True)
    candle_rows = candles_to_csv_rows(sorted(all_candles, key=lambda c: (c.symbol, c.timeframe, c.timestamp)))
    with (output_dir / "candles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candle_rows[0].keys()))
        writer.writeheader()
        writer.writerows(candle_rows)
    report = engine.results()
    report["market_data"] = {
        "provider": "Bitget USDT-FUTURES",
        "symbols": sorted({c.symbol for c in all_candles}),
        "timeframes": sorted({c.timeframe for c in all_candles}),
        "candles_downloaded": len(all_candles),
        "signals_verified_against_closed_candles": len(signals),
        "range_start_utc": start.isoformat(),
        "range_end_utc": end.isoformat(),
        "signal_generation": "external confirmed signals; no signal rules inferred by this runner",
    }
    write_json(output_dir / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the V1 Vegas historical trade simulation.")
    parser.add_argument("--start", required=True, help="UTC ISO date/time, e.g. 2025-01-01T00:00:00Z")
    parser.add_argument("--end", required=True, help="UTC ISO date/time, e.g. 2026-01-01T00:00:00Z")
    parser.add_argument("--signals", required=True, type=Path, help="JSON list of pre-confirmed Vegas signals")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    try:
        report = run(parse_datetime(args.start), parse_datetime(args.end), args.signals, args.output_dir)
    except Exception as exc:
        print(f"V1 backtest failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "summary": report["summary"],
        "market_data": report["market_data"],
        "report_file": str(args.output_dir / "report.json"),
        "candles_file": str(args.output_dir / "candles.csv"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
