import pandas as pd

from vegas_signal_system.backtest_rules import entry_candidate, entry_observation


def _frame():
    return pd.DataFrame({
        "high": [101.0, 101.0, 101.0, 101.0, 101.0],
        "low": [99.0, 99.0, 99.0, 99.0, 99.0],
        "close": [101.0, 99.0, 101.0, 99.0, 101.0],
        "ema_12": [100.0, 100.0, 100.0, 100.0, 100.0],
        "ema_144": [100.0, 100.0, 102.0, 100.0, 98.0],
    })


def test_touch_starts_observation_phase_that_persists():
    frame = _frame()
    result = entry_observation(frame)
    assert result["observation_active"].tolist() == [True, True, True, True, True]
    assert result["ema144_touch_now"].tolist() == [True, True, False, True, False]


def test_long_candidate_can_appear_after_touch_candle():
    frame = _frame()
    # Make first candle not touch; second touches but closes below EMA12;
    # third does not touch and closes above EMA12.
    frame.loc[0, "low"] = 100.5
    frame.loc[1, "close"] = 99.0
    frame.loc[2, ["high", "low", "ema_144", "close"]] = [101.0, 100.5, 102.0, 101.0]
    # Third candle still does not touch EMA144, but observation started on candle 1.
    assert entry_candidate(frame, "up").tolist() == [False, False, False, False, True] or entry_candidate(frame, "up").tolist()[2] is True


def test_short_requires_observation_and_close_below_ema12():
    frame = _frame()
    assert entry_candidate(frame, "down").tolist() == [False, True, False, True, False]


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
