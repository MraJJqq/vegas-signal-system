from __future__ import annotations

import unittest

from historical_reversal import bullish_reversal_indices


class HistoricalReversalTests(unittest.TestCase):
    def test_confirms_close_above_pullback_above_sequence(self):
        closes = [101, 99, 102]
        ema36 = [95, 95, 96]
        ema144 = [100, 100, 100]
        self.assertEqual(bullish_reversal_indices(closes, ema36, ema144), [2])

    def test_close_breaking_ema36_invalidates_sequence(self):
        closes = [101, 94, 99, 102]
        ema36 = [95, 95, 95, 96]
        ema144 = [100, 100, 100, 100]
        self.assertEqual(bullish_reversal_indices(closes, ema36, ema144), [])

    def test_requires_closed_price_below_or_at_middle_for_pullback(self):
        closes = [101, 100.5, 102]
        ema36 = [95, 95, 96]
        ema144 = [100, 100, 100]
        self.assertEqual(bullish_reversal_indices(closes, ema36, ema144), [])

    def test_rejects_mismatched_series(self):
        with self.assertRaises(ValueError):
            bullish_reversal_indices([1], [0], [])


if __name__ == "__main__":
    unittest.main()
