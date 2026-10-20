import pandas as pd

from vegas_signal_system.backtest_rules import entry_candidate


def _frame():
    return pd.DataFrame({
        "high": [101.0, 101.0, 101.0, 101.0],
        "low": [99.0, 99.0, 99.0, 99.0],
        "close": [101.0, 99.0, 101.0, 99.0],
        "ema_12": [100.0, 100.0, 100.0, 100.0],
        "ema_144": [100.0, 100.0, 102.0, 98.0],
    })


def test_long_requires_touch_and_close_above_ema12():
    assert entry_candidate(_frame(), "up").tolist() == [True, False, False, False]


def test_short_requires_touch_and_close_below_ema12():
    assert entry_candidate(_frame(), "down").tolist() == [False, True, False, False]


def test_neutral_direction_never_emits_candidate():
    assert not entry_candidate(_frame(), "neutral").any()


def test_missing_indicator_column_fails_clearly():
    frame = _frame().drop(columns=["ema_12"])
    try:
        entry_candidate(frame, "up")
    except ValueError as exc:
        assert "ema_12" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
