"""
VEGAS V1 Trading System (简称 V1) — isolated from the V3 signal system.

This module implements the backtest execution/risk framework only. Vegas signal
generation must be supplied as confirmed, closed-candle SignalEvent records;
this file deliberately does not invent or reinterpret the user's signal rules.

Rules encoded:
- Entry at the signal candle close.
- Observation has no timeout (observation is upstream of this engine).
- Higher timeframe valid signal wins for the same symbol when signals are
  presented together for the same decision timestamp.
- BTC/HYPE: the first valid crypto signal claims crypto trade eligibility.
- Isolated margin budgets: 10 USDT base, 5 USDT reversal trial.
- Add-ons require a new valid signal and halve the budget each time.
- Reversal closes 80% of the original-trend exposure, retains 20%, and opens
  a 5 USDT opposite trial position. Trial positions are not actively closed;
  they remain open until an externally verified liquidation event.
- No initial account balance or account-return calculation.
- Synthetic candles created for small gaps are explicitly marked.

No leverage, liquidation price, or intrabar path is inferred here. Liquidation
events must be supplied by a data/execution adapter using verified information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, Optional, Sequence


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def opposite(self) -> "Direction":
        return Direction.SHORT if self is Direction.LONG else Direction.LONG


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    is_closed: bool = True
    is_synthetic: bool = False

    def validate(self) -> None:
        if not self.is_closed:
            raise ValueError("Backtest input must contain closed candles only.")
        if not all(v > 0 for v in (self.open, self.high, self.low, self.close)):
            raise ValueError("OHLC prices must be positive.")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("Invalid candle: high is below another OHLC value.")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Invalid candle: low is above another OHLC value.")


@dataclass(frozen=True)
class SignalEvent:
    """A valid Vegas signal already confirmed by the upstream rule evaluator."""
    symbol: str
    timeframe: str
    timestamp: datetime
    direction: Direction
    signal_close: float
    valid: bool = True
    is_synthetic_source: bool = False

    def validate(self) -> None:
        if not self.valid:
            raise ValueError("Invalid signal events must not be executed.")
        if self.signal_close <= 0:
            raise ValueError("Signal close must be positive.")
        if self.timeframe not in {"1H", "2H", "4H", "8H"}:
            raise ValueError(f"Unsupported timeframe: {self.timeframe}")


@dataclass
class Position:
    position_id: int
    symbol: str
    direction: Direction
    margin_budget: float
    entry_price: float
    entry_time: datetime
    timeframe: str
    kind: str = "main"
    is_open: bool = True
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    synthetic_entry: bool = False
    parent_position_id: Optional[int] = None
    exposure_fraction: float = 1.0

    @property
    def simplified_max_loss(self) -> float:
        """User-defined approximation, ignoring fees, slippage and funding."""
        return self.margin_budget


@dataclass(frozen=True)
class TradeRecord:
    event: str
    timestamp: datetime
    symbol: str
    details: str
    price: Optional[float] = None
    margin_budget: Optional[float] = None
    synthetic_data_involved: bool = False


@dataclass
class BacktestReport:
    trades: list[TradeRecord] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    synthetic_candle_count: int = 0
    real_candle_count: int = 0

    def summary(self) -> dict:
        closed = [p for p in self.positions if not p.is_open]
        return {
            "trade_events": len(self.trades),
            "positions_opened": len(self.positions),
            "positions_closed": len(closed),
            "positions_still_open": sum(p.is_open for p in self.positions),
            "synthetic_candles": self.synthetic_candle_count,
            "real_candles": self.real_candle_count,
            "initial_account_balance": None,
            "account_return": None,
            "note": "No account balance or account return is calculated.",
        }


TIMEFRAME_RANK = {"1H": 1, "2H": 2, "4H": 3, "8H": 4}
BASE_MARGIN = 10.0
REVERSAL_TRIAL_MARGIN = 5.0
CRYPTO_COMPETITION_SYMBOLS = {"BTC", "HYPE"}


def fill_small_gaps(
    candles: Sequence[Candle],
    timeframe: str,
    max_missing_candles: int = 2,
) -> list[Candle]:
    """Fill only small timestamp gaps using previous close; mark every fill.

    Candles must be sorted by timestamp. Larger gaps are left untouched and
    should be reported by the data-ingestion layer rather than silently filled.
    """
    if timeframe not in {"1H", "2H", "4H", "8H"}:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if max_missing_candles < 0:
        raise ValueError("max_missing_candles cannot be negative.")

    step_hours = int(timeframe[:-1])
    step = timedelta(hours=step_hours)
    ordered = sorted(candles, key=lambda c: c.timestamp)
    if not ordered:
        return []

    output: list[Candle] = []
    for candle in ordered:
        candle.validate()
        if output:
            previous = output[-1]
            if candle.symbol != previous.symbol or candle.timeframe != previous.timeframe:
                raise ValueError("Pass one symbol/timeframe series at a time.")
            gap = candle.timestamp - previous.timestamp
            if gap.total_seconds() <= 0:
                raise ValueError("Duplicate or out-of-order candle timestamps.")
            missing = int(gap / step) - 1
            if missing > 0 and missing <= max_missing_candles:
                cursor = previous.timestamp + step
                for _ in range(missing):
                    close = previous.close
                    synthetic = Candle(
                        symbol=previous.symbol,
                        timeframe=previous.timeframe,
                        timestamp=cursor,
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        is_closed=True,
                        is_synthetic=True,
                    )
                    output.append(synthetic)
                    previous = synthetic
                    cursor += step
        output.append(candle)
    return output


def prioritize_same_symbol_signals(
    signals: Iterable[SignalEvent],
) -> list[SignalEvent]:
    """For a shared decision timestamp, keep the highest timeframe per symbol."""
    grouped: dict[tuple[str, datetime], list[SignalEvent]] = {}
    for signal in signals:
        signal.validate()
        grouped.setdefault((signal.symbol, signal.timestamp), []).append(signal)

    selected: list[SignalEvent] = []
    for group in grouped.values():
        group.sort(key=lambda s: TIMEFRAME_RANK[s.timeframe], reverse=True)
        selected.append(group[0])
    return sorted(selected, key=lambda s: (s.timestamp, s.symbol))


class VegasBacktestV2:
    """Execution ledger; signal detection remains an external, rule-tested layer."""

    def __init__(self) -> None:
        self.report = BacktestReport()
        self._next_position_id = 1
        self._crypto_claimed_by: Optional[str] = None
        self._addon_count: dict[str, int] = {}
        self._main_position_ids: dict[str, list[int]] = {}

    def record_candles(self, candles: Iterable[Candle]) -> None:
        for candle in candles:
            candle.validate()
            if candle.is_synthetic:
                self.report.synthetic_candle_count += 1
            else:
                self.report.real_candle_count += 1

    def _new_position(
        self,
        *,
        symbol: str,
        direction: Direction,
        margin: float,
        price: float,
        timestamp: datetime,
        timeframe: str,
        kind: str,
        synthetic: bool = False,
        parent_position_id: Optional[int] = None,
        exposure_fraction: float = 1.0,
    ) -> Position:
        position = Position(
            position_id=self._next_position_id,
            symbol=symbol,
            direction=direction,
            margin_budget=margin,
            entry_price=price,
            entry_time=timestamp,
            timeframe=timeframe,
            kind=kind,
            synthetic_entry=synthetic,
            parent_position_id=parent_position_id,
            exposure_fraction=exposure_fraction,
        )
        self._next_position_id += 1
        self.report.positions.append(position)
        return position

    def process_signals(self, signals: Iterable[SignalEvent]) -> list[Position]:
        """Open eligible signals at their signal-candle close.

        Signals with the same symbol and timestamp are reduced to the highest
        timeframe first. BTC/HYPE compete for the first valid crypto entry;
        after one claims eligibility, the other is ignored by this run.
        """
        opened: list[Position] = []
        selected = prioritize_same_symbol_signals(signals)
        for signal in selected:
            if not signal.valid:
                continue
            if signal.symbol in CRYPTO_COMPETITION_SYMBOLS:
                if self._crypto_claimed_by is None:
                    self._crypto_claimed_by = signal.symbol
                elif self._crypto_claimed_by != signal.symbol:
                    self.report.trades.append(TradeRecord(
                        event="signal_ignored",
                        timestamp=signal.timestamp,
                        symbol=signal.symbol,
                        details=f"Crypto eligibility already claimed by {self._crypto_claimed_by}.",
                        price=signal.signal_close,
                        synthetic_data_involved=signal.is_synthetic_source,
                    ))
                    continue

            existing = [
                p for p in self.report.positions
                if p.symbol == signal.symbol and p.is_open and p.kind == "main"
            ]
            if existing:
                # Every add-on requires a new valid signal. This event is a new
                # valid signal; budgets halve with each successive add-on.
                count = self._addon_count.get(signal.symbol, 0) + 1
                margin = BASE_MARGIN / (2 ** count)
                position = self._new_position(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    margin=margin,
                    price=signal.signal_close,
                    timestamp=signal.timestamp,
                    timeframe=signal.timeframe,
                    kind="addon",
                    synthetic=signal.is_synthetic_source,
                )
                self._addon_count[signal.symbol] = count
                self._main_position_ids.setdefault(signal.symbol, []).append(position.position_id)
                self.report.trades.append(TradeRecord(
                    event="addon_open",
                    timestamp=signal.timestamp,
                    symbol=signal.symbol,
                    details=f"Add-on #{count}; margin budget halves from base.",
                    price=signal.signal_close,
                    margin_budget=margin,
                    synthetic_data_involved=signal.is_synthetic_source,
                ))
            else:
                position = self._new_position(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    margin=BASE_MARGIN,
                    price=signal.signal_close,
                    timestamp=signal.timestamp,
                    timeframe=signal.timeframe,
                    kind="main",
                    synthetic=signal.is_synthetic_source,
                )
                self._addon_count[signal.symbol] = 0
                self._main_position_ids.setdefault(signal.symbol, []).append(position.position_id)
                self.report.trades.append(TradeRecord(
                    event="entry",
                    timestamp=signal.timestamp,
                    symbol=signal.symbol,
                    details="Entry at the confirmed signal candle close.",
                    price=signal.signal_close,
                    margin_budget=BASE_MARGIN,
                    synthetic_data_involved=signal.is_synthetic_source,
                ))
            opened.append(position)
        return opened

    def confirm_reversal(
        self,
        *,
        symbol: str,
        opposite_direction: Direction,
        timestamp: datetime,
        price: float,
        timeframe: str = "1H",
        reversal_structure_confirmed: bool,
        synthetic_source: bool = False,
    ) -> Optional[Position]:
        """Apply the user's reversal consequence only after structure confirmation.

        The caller must verify the full 1H middle-line -> pioneer pullback ->
        re-stand-above-middle-line sequence using closed candles. This method
        does not guess EMA values or infer the sequence from incomplete data.
        """
        if not reversal_structure_confirmed:
            return None
        if timeframe != "1H":
            raise ValueError("Reversal confirmation must use the 1H timeframe.")
        if price <= 0:
            raise ValueError("Reversal price must be positive.")

        mains = [
            p for p in self.report.positions
            if p.symbol == symbol and p.is_open and p.kind in {"main", "addon"}
        ]
        if not mains:
            return None

        # Reduce each open original-trend position by 80%; retain 20%.
        # Margin budget and exposure fraction are tracked separately so the
        # report can preserve the original position record.
        for position in mains:
            original_direction = position.direction
            if original_direction is opposite_direction:
                continue
            closed_fraction = 0.80 * position.exposure_fraction
            position.exposure_fraction *= 0.20
            self.report.trades.append(TradeRecord(
                event="reversal_reduce",
                timestamp=timestamp,
                symbol=symbol,
                details=(
                    f"Closed {closed_fraction:.2%} of this position's current exposure; "
                    f"{position.exposure_fraction:.2%} of original exposure remains."
                ),
                price=price,
                margin_budget=position.margin_budget * 0.80,
                synthetic_data_involved=synthetic_source,
            ))

        trial = self._new_position(
            symbol=symbol,
            direction=opposite_direction,
            margin=REVERSAL_TRIAL_MARGIN,
            price=price,
            timestamp=timestamp,
            timeframe="1H",
            kind="reversal_trial",
            synthetic=synthetic_source,
        )
        self.report.trades.append(TradeRecord(
            event="reversal_trial_open",
            timestamp=timestamp,
            symbol=symbol,
            details="5 USDT opposite trial; no active exit before verified liquidation.",
            price=price,
            margin_budget=REVERSAL_TRIAL_MARGIN,
            synthetic_data_involved=synthetic_source,
        ))
        return trial

    def mark_liquidated(
        self,
        position_id: int,
        *,
        timestamp: datetime,
        liquidation_price: Optional[float] = None,
        liquidation_verified: bool = False,
    ) -> None:
        """Close a position only when an external adapter confirms liquidation."""
        if not liquidation_verified:
            raise ValueError("Liquidation must be externally verified.")
        position = next(
            (p for p in self.report.positions if p.position_id == position_id),
            None,
        )
        if position is None:
            raise KeyError(f"Unknown position_id: {position_id}")
        if not position.is_open:
            raise ValueError("Position is already closed.")
        position.is_open = False
        position.exit_price = liquidation_price
        position.exit_time = timestamp
        position.exit_reason = "liquidation"
        self.report.trades.append(TradeRecord(
            event="liquidation",
            timestamp=timestamp,
            symbol=position.symbol,
            details=(
                "Simplified loss equals margin budget; ignored costs per user rule."
            ),
            price=liquidation_price,
            margin_budget=position.margin_budget,
            synthetic_data_involved=position.synthetic_entry,
        ))

    def results(self) -> dict:
        return {
            "summary": self.report.summary(),
            "trade_events": [
                {
                    "event": t.event,
                    "timestamp": t.timestamp.isoformat(),
                    "symbol": t.symbol,
                    "details": t.details,
                    "price": t.price,
                    "margin_budget": t.margin_budget,
                    "synthetic_data_involved": t.synthetic_data_involved,
                }
                for t in self.report.trades
            ],
            "positions": [
                {
                    "position_id": p.position_id,
                    "symbol": p.symbol,
                    "direction": p.direction.value,
                    "margin_budget": p.margin_budget,
                    "entry_price": p.entry_price,
                    "entry_time": p.entry_time.isoformat(),
                    "timeframe": p.timeframe,
                    "kind": p.kind,
                    "is_open": p.is_open,
                    "exit_price": p.exit_price,
                    "exit_time": p.exit_time.isoformat() if p.exit_time else None,
                    "exit_reason": p.exit_reason,
                    "synthetic_entry": p.synthetic_entry,
                    "exposure_fraction": p.exposure_fraction,
                }
                for p in self.report.positions
            ],
        }
