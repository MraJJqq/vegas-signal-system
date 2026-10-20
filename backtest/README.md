# Gold backtest framework — entry observation rules

## Entry observation phase

Evaluate 1H and 2H independently. On each timeframe, use that timeframe's own EMA12 and EMA144.

1. A completed candle whose high-low range spans EMA144 is the OHLC-data proxy for price having touched EMA144.
2. That touch starts an observation phase. The phase remains active on later candles, even if those candles no longer touch EMA144.
3. During the observation phase, check each completed candle's close against that timeframe's EMA12:
   - Long candidate: close above EMA12, with the higher-timeframe direction gate allowing longs.
   - Short candidate: close below EMA12, with the higher-timeframe direction gate allowing shorts.
   - Close exactly on EMA12: neither side.
4. A 1H observation uses 1H EMA12/EMA144; a 2H observation uses 2H EMA12/EMA144. Never mix timeframes.

The observation phase currently has no reset/expiry condition. This is intentionally left explicit for a later rule decision, rather than inventing an expiry. Because OHLC candles do not contain tick-by-tick paths, the high/low spanning EMA144 is a data-level proxy for contact, not proof of the exact intrabar path.

This module marks candidate candles; it does not itself simulate fills, stop loss, or exits, and does not claim a backtest performance result.

## No-lookahead requirements

- Use completed candles only.
- EMA values use current and past closes only.
- A signal is known at candle close; a simulated fill must not occur earlier than the next available executable price.
