# V2 Validation Plan

## Data integrity
- [ ] Reject or explicitly report duplicate timestamps.
- [ ] Report missing candles and timezone inconsistencies.
- [ ] Use completed candles only.
- [ ] Prove 4H/8H alignment has no future-data leakage.
- [ ] Keep unavailable timeframe values unavailable.

## Rule contract
- [ ] Opposite 4H and 8H directions produce no-trade.
- [ ] Matching direction sources permit continued setup evaluation.
- [ ] Touch is true only when candle high >= EMA144 and candle low <= EMA144.
- [ ] A touch alone never creates an entry signal.
- [ ] Long confirmation requires completed close > EMA12.
- [ ] Short confirmation requires completed close < EMA12.
- [ ] Signal logic cannot run with invalid/missing required inputs.

## Operations
- [ ] Repeated scans do not send duplicate alerts for the same signal event.
- [ ] ntfy failures are logged and retried safely.
- [ ] Secrets are loaded from environment/repository secrets, not committed files.
- [ ] No order-execution behavior exists.

## Release gate
Do not describe V2 as autonomous or production-ready until all required tests pass and a live-data dry run has been verified.
