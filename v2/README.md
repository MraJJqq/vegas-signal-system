# Vegas Signal System V2

## Purpose
A new, isolated V2 implementation area for the Vegas signal reminder system. This branch is `v2-storage`.

## Scope
- Monitor market data and produce signal reminders only.
- No automatic order execution.
- Keep market-data acquisition, timeframe alignment, rule evaluation, risk checks, scheduling, and ntfy delivery as separate modules.
- Never silently change or relax the user's Vegas rules.

## Rule invariants
1. 4H and 8H are independent direction sources.
2. If 4H and 8H directions conflict, return no-trade.
3. When direction filter passes, wait for price to touch the relevant 1H or 2H EMA144 中锋; touch means candle high >= EMA144 and candle low <= EMA144.
4. Entry confirmation uses a completed candle: close above EMA12 for long, below EMA12 for short, after the required touch.
5. EMA36 is 先锋; EMA144 is 中锋; EMA576 is 大资金 reference where data exists.
6. Missing timeframe data stays unavailable/blank; do not fabricate or forward-fill future information.
7. No lookahead: only completed candles and information available at the decision timestamp may be used.
8. Signal reminders only; the user makes the final trade decision.

Any proposed rule change requires explicit user approval before implementation.

## Planned layout
- `v2/README.md` — project contract and structure
- `v2/settings.example.yaml` — non-secret example configuration
- `v2/docs/architecture.md` — module boundaries and data flow
- `v2/docs/validation-plan.md` — acceptance tests
- `v2/src/vegas_signal_v2/` — implementation modules (to be added after contract review)
- `v2/tests/` — automated tests

## Secrets
Never commit API keys, ntfy tokens, passwords, or account credentials. Use environment variables or repository secrets.

## Status
Storage scaffold created. No live scanner or automated execution is claimed to be operational yet.
