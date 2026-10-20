# V2 Architecture

## Pipeline
1. **Market data provider** — fetch OHLCV and normalize timestamps/symbols.
2. **Data validator** — check duplicates, gaps, timezone, candle completion, and missing intervals.
3. **Indicator engine** — calculate EMA12, EMA36, EMA144, and EMA576 without lookahead.
4. **Timeframe aligner** — expose only completed 4H/8H direction data available at the current decision time.
5. **Rule engine** — apply the frozen Vegas direction, touch, and entry confirmation contract.
6. **Risk validator** — report configured risk checks; never place orders.
7. **Scheduler/scanner** — run scans on a defined schedule and avoid duplicate alerts.
8. **Notifier** — send signal summaries to ntfy; never include credentials in logs.

## Required signal states
- `NO_TRADE_DIRECTION_CONFLICT`
- `WAITING_FOR_MIDDLE_LINE_TOUCH`
- `WAITING_FOR_ENTRY_CONFIRMATION`
- `SIGNAL_LONG`
- `SIGNAL_SHORT`
- `DATA_UNAVAILABLE`
- `DATA_INVALID`

## Safety boundaries
- No order-placement module or exchange trading permission is required.
- A data outage must not be interpreted as a trading signal.
- A missing 4H/8H value remains unavailable; do not invent a direction.
- Any rule-affecting ambiguity must be surfaced for approval rather than silently decided.
