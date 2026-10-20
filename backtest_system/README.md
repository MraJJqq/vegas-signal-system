# VEGAS AI TRADING — Backtest System

> **Scope boundary:** This directory documents the independent backtest system only. Do not modify signal-system source code as part of backtest work. This document records the user's confirmed V2 rules; it is not permission to alter those rules.

## Status

- Rules baseline: **V2 — user-confirmed**
- Purpose: historical research and backtesting; no live order execution.
- Change policy: technical implementation and data-quality defects may be fixed, but strategy rules must not be changed, relaxed, replaced, or reinterpreted without the user's explicit approval.
- Reporting policy: report observed results honestly; do not predefine a pass/fail threshold.

## 1. Entry

- Enter at the signal candle's closing price.
- An observation state has no time limit.
- Use only completed candles for signals and fills. Never use future data.

## 2. Timeframe and market qualification

- For the same instrument, prefer the valid signal from the higher timeframe when multiple timeframes qualify.
- For cryptocurrency qualification, BTC and HYPE compete: the instrument whose valid signal occurs first obtains trading eligibility.
- These are separate priority layers: first determine BTC/HYPE eligibility by the first valid signal, then apply higher-timeframe priority within the eligible instrument. Do not let a later signal retroactively replace the first qualification.
- Implementations must not invent tie-breaking behavior for simultaneous timestamps; document it as unresolved until verified from the original recorded answers or explicitly confirmed by the user.

## 3. Margin and simplified loss model

- Normal initial position margin: **10 USDT**.
- Reverse trial position margin: **5 USDT**.
- Use isolated margin; do not use cross margin.
- For this backtest's simplified model, ignore fees and other trading costs.
- Approximate a liquidation loss as the margin allocated to that position. This is a modeling assumption, not a claim about exact exchange liquidation mechanics.
- Do not confuse position margin with account-equity risk or infer an account return: no initial account balance is specified.

## 4. Add-ons

- Add-on count is unlimited under the stated rule.
- Margin allocated to successive normal add-ons follows a halving sequence: **10, 5, 2.5, 1.25 USDT, ...**
- Keep the initial normal position, add-on sequence, and separate 5 USDT reverse trial position distinct in code and reports.
- Do not add unapproved caps or change the sequence.

## 5. Reversal and reverse trial

- Confirm reversal only after the full specified **1H structure**: 中锋 (middle EMA/line) → 先锋 (pioneer EMA/line) pullback → price stands back above 中锋.
- Preserve the named structure and the 1H timeframe. Do not substitute a different reversal signal.
- The exact EMA periods and detailed candle-by-candle predicate must be read from the existing authoritative project rules/code or original user answers. Do not guess missing parameters.
- Once the reversal is confirmed, close **80% of the original-trend total position**, retain **20%**, and open an opposite-direction **5 USDT** trial position.
- The reverse trial position is not actively closed; hold it until its modeled liquidation. Do not add a discretionary exit or reuse an older, conflicting trial-exit rule.

## 6. Market data and missing candles

- Use valid historical market data from **Bitget** as far as available. Do not silently replace the requested source with Yahoo Finance or another provider.
- A small number of missing candles may be filled using the previous candle's close, with the resulting candles explicitly marked as **synthetic**.
- Synthetic candles must never be presented as genuine exchange observations.
- The numerical threshold for what counts as a “small number” of missing candles is not specified in this baseline. Check the original recorded answers or existing authoritative implementation; if it cannot be recovered, report it as unresolved rather than inventing a threshold.
- Track source, timestamps, missing intervals, and synthetic-data flags. Prevent future-data leakage and preserve chronological ordering.

## 7. Results and reporting

- Report actual observed backtest results only.
- Do not invent or impose a pass/fail threshold.
- No initial account balance is specified; do not calculate or report account-level return percentages.
- Clearly distinguish raw exchange data from synthetic/fill data and disclose data limitations.
- Report trade-level and aggregate measurements that can be computed from the actual data and implemented rules, without implying that unverified results are validated.

## 8. Required implementation checks

Before treating a result as rule-compliant, verify:

1. Entries occur at the signal candle close and use completed candles only.
2. No future data is used in signals, timeframe alignment, or fills.
3. Higher-timeframe priority is applied within the eligible instrument.
4. BTC/HYPE eligibility is assigned by the first valid signal, without retroactive reassignment.
5. Normal position/add-on margins follow 10 → 5 → 2.5 → 1.25 USDT and continue halving.
6. Reversal uses the full specified 1H 中锋 → 先锋 pullback → regain 中锋 structure.
7. Reversal closes 80% of the original-trend total position, retains 20%, and opens an opposite 5 USDT trial position.
8. The reverse trial is held to modeled liquidation, with no unapproved active exit.
9. Bitget is the historical data source; synthetic candles are marked and never misrepresented.
10. Reports contain actual results only, with no invented pass threshold or account return percentage.

## 9. Unresolved details — do not guess

- Exact EMA periods and formal candle predicates for the 1H reversal structure, unless already specified in the authoritative project rules/code.
- The numerical threshold for “a small number” of missing candles.
- A tie-break policy if BTC and HYPE valid signals have exactly the same timestamp.
- Any further details from the original multi-question rules session that are not represented here.

Resolve these by consulting the original recorded user answers or existing authoritative project artifacts. Ask the user only if the source cannot be recovered and the missing detail is necessary. Do not silently fill gaps with assumptions.

## Change log

- Initial commit: recorded the user-confirmed V2 backtest rules and implementation boundaries.
