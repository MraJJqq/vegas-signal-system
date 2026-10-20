# Gold backtest framework — first milestone

This module defines the agreed entry-candidate rule for the gold (XAUUSDT) backtest.

## Entry candidate rule

Evaluate 1H and 2H independently. On the evaluated timeframe, a candle qualifies only when:

1. Its high-low range covers EMA144 (the 中锋 touch rule).
2. For an up-direction setup, that candle closes above its own EMA12 filter.
3. For a down-direction setup, that candle closes below its own EMA12 filter.
4. Direction is supplied by the higher-timeframe Vegas direction gate; neutral or unknown direction produces no candidate.

A 1H candidate uses the 1H candle and 1H EMA12/EMA144. A 2H candidate uses the 2H candle and 2H EMA12/EMA144. Do not mix indicators across timeframes.

This milestone creates candidate detection only. It does not claim that a trade was filled, does not invent stop/exit rules, and does not report performance statistics until candle-by-candle execution, stop/exit mechanics, and data-quality checks are implemented and tested.

## Data and no-lookahead requirements

- Use completed candles only.
- EMA values use current and past closes only.
- Signal timestamp is the close time of the qualifying candle; a simulated fill must not occur earlier than the next available executable price.
- Keep 1H and 2H candidate records identifiable by timeframe.
