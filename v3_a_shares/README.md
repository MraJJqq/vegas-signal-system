# V3 A-share data-source pilot (not enabled)

This folder is intentionally separate from `v3/`. It does not change the
existing Bitget scan, V3 Vegas rules, notification settings, or GitHub Actions
configuration.

## Current implementation

- AKShare + Eastmoney 60-minute history, requested with `adjust="qfq"`.
- Main-board code-prefix screening for Shanghai/Shenzhen only.
- Excludes stocks whose live snapshot price is missing, invalid, or non-positive.
- Aggregates four 60-minute bars into one four-trading-hour session candle:
  09:30-11:30 and 13:00-15:00, with lunch break excluded.
- Uses completed sessions only; incomplete sessions are discarded.
- Fails closed if fewer than 676 complete session candles are available, because
  V3 computes EMA676. It never invents candles or evaluates signals without
  sufficient history.

## Important limitations to validate before enabling

1. The AKShare/Eastmoney 60-minute endpoint may not provide 676 complete
   historical sessions for every symbol. The adapter deliberately reports this
   instead of falling back to daily bars.
2. Forward-adjusted historical minute bars and their long-term coverage must
   be verified against live responses. This code requests qfq but does not
   claim the provider has passed validation.
3. A zero/missing live price is treated as inactive and excluded. The snapshot
   alone cannot distinguish suspension from all other data-quality problems;
   provider failures raise errors rather than counting as a successful scan.
4. Main-board code prefixes are an initial universe filter; validate against
   official exchange classifications before production.
5. No workflow was added and no GitHub configuration was changed. This pilot
   is not yet running on a schedule and sends no notifications.

## Local test

Install dependencies:

```bash
python -m pip install akshare pandas
```

Run offline unit tests:

```bash
cd v3_a_shares
python -m unittest -v
```

A successful unit test run validates code behavior with mocked data only. A
separate live-data test is still required before enabling full-market scans.


## Focused scan pool

The initial watchlist is defined in `universe.json` and contains 12 liquid Shanghai/Shenzhen main-board candidates across consumer, banking, metals, utilities, manufacturing, semiconductors, pharmaceuticals, and industrial equipment. It excludes ChiNext, STAR Market, and Beijing-listed stocks. This is a candidate universe, not a claim that each stock currently has a clear Vegas trend. The Vegas rules must decide whether a formal signal exists.

The pool remains `pilot_not_enabled` until live-data validation confirms sufficient complete 4H session candles for EMA676 and suspension handling. No A-share signal is sent by this configuration alone.

## Automated validation

The isolated workflow `.github/workflows/ashare-data-validation.yml` runs offline unit tests and a live-data smoke test. It does not enable scheduled scanning or send notifications.
