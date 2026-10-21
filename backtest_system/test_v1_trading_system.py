from datetime import datetime, timedelta, timezone
import unittest

from v1_trading_system import (
    Candle, Direction, SignalEvent, VegasBacktestV2,
    fill_small_gaps, prioritize_same_symbol_signals,
)


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def signal(symbol="GOLDUSDT", timeframe="4H", offset=0, price=100.0, direction=Direction.LONG):
    return SignalEvent(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=T0 + timedelta(hours=offset),
        direction=direction,
        signal_close=price,
    )


class V1TradingSystemTests(unittest.TestCase):
    def test_entry_uses_signal_close_and_10u_margin(self):
        engine = VegasBacktestV2()
        opened = engine.process_signals([signal(price=123.45)])
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].entry_price, 123.45)
        self.assertEqual(opened[0].margin_budget, 10.0)
        self.assertEqual(opened[0].kind, "main")

    def test_addon_budget_halves_for_each_new_signal(self):
        engine = VegasBacktestV2()
        engine.process_signals([signal(offset=0)])
        p2 = engine.process_signals([signal(offset=4)])[0]
        p3 = engine.process_signals([signal(offset=8)])[0]
        self.assertEqual([p2.margin_budget, p3.margin_budget], [5.0, 2.5])
        self.assertEqual([p2.kind, p3.kind], ["addon", "addon"])

    def test_opposite_signal_is_not_misclassified_as_addon(self):
        engine = VegasBacktestV2()
        first = engine.process_signals([
            signal(direction=Direction.LONG, offset=0)
        ])[0]
        opened = engine.process_signals([
            signal(direction=Direction.SHORT, offset=4)
        ])
        self.assertEqual(opened, [])
        self.assertEqual(len(engine.report.positions), 1)
        self.assertTrue(first.is_open)
        self.assertEqual(
            [t.event for t in engine.report.trades],
            ["entry", "opposite_signal_ignored"],
        )

    def test_highest_timeframe_wins_for_same_symbol_and_timestamp(self):
        chosen = prioritize_same_symbol_signals([
            signal(timeframe="1H", offset=0, price=100),
            signal(timeframe="4H", offset=0, price=101),
            signal(timeframe="2H", offset=0, price=102),
        ])
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0].timeframe, "4H")
        self.assertEqual(chosen[0].signal_close, 101)

    def test_small_gap_fill_is_marked_and_uses_previous_close(self):
        candles = [
            Candle("GOLDUSDT", "4H", T0, 100, 102, 99, 101),
            Candle("GOLDUSDT", "4H", T0 + timedelta(hours=8), 103, 104, 102, 103),
        ]
        result = fill_small_gaps(candles, "4H", max_missing_candles=2)
        self.assertEqual(len(result), 3)
        self.assertTrue(result[1].is_synthetic)
        self.assertEqual(result[1].open, 101)
        self.assertEqual(result[1].close, 101)

    def test_reversal_requires_confirmation_and_opens_5u_trial(self):
        engine = VegasBacktestV2()
        main = engine.process_signals([signal()])[0]
        no_trial = engine.confirm_reversal(
            symbol="GOLDUSDT", opposite_direction=Direction.SHORT,
            timestamp=T0 + timedelta(hours=1), price=99,
            reversal_structure_confirmed=False,
        )
        self.assertIsNone(no_trial)
        trial = engine.confirm_reversal(
            symbol="GOLDUSDT", opposite_direction=Direction.SHORT,
            timestamp=T0 + timedelta(hours=2), price=98,
            reversal_structure_confirmed=True,
        )
        self.assertEqual(main.exposure_fraction, 0.2)
        self.assertEqual(trial.margin_budget, 5.0)
        self.assertEqual(trial.kind, "reversal_trial")
        self.assertTrue(trial.is_open)

    def test_liquidation_requires_external_verification(self):
        engine = VegasBacktestV2()
        p = engine.process_signals([signal()])[0]
        with self.assertRaises(ValueError):
            engine.mark_liquidated(p.position_id, timestamp=T0, liquidation_verified=False)
        engine.mark_liquidated(p.position_id, timestamp=T0, liquidation_verified=True)
        self.assertFalse(p.is_open)
        self.assertEqual(p.exit_reason, "liquidation")

    def test_account_return_is_not_calculated(self):
        result = VegasBacktestV2().results()["summary"]
        self.assertIsNone(result["initial_account_balance"])
        self.assertIsNone(result["account_return"])


if __name__ == "__main__":
    unittest.main()
