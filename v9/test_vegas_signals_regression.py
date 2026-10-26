"""Regression tests for V9 Vegas-zone touch semantics."""
from vegas_signals import LINES, _touched_zones


def test_middle_of_band_counts_as_touch_even_when_no_single_ema_is_crossed():
    values = {label: [None] * 1 for label, _period in LINES}
    values["中锋EMA144"] = [100.0]
    values["中锋EMA169"] = [110.0]
    values["红峰EMA576"] = [200.0]
    values["红峰EMA676"] = [220.0]
    # The candle range sits inside the band, not across either boundary line.
    assert _touched_zones(104.0, 106.0, values, 0) == ["中锋EMA144", "中锋EMA169"]


def test_candle_outside_both_bands_does_not_touch():
    values = {label: [None] * 1 for label, _period in LINES}
    values["中锋EMA144"] = [100.0]
    values["中锋EMA169"] = [110.0]
    values["红峰EMA576"] = [200.0]
    values["红峰EMA676"] = [220.0]
    assert _touched_zones(120.0, 130.0, values, 0) == []


def test_touch_at_band_boundary_counts_as_overlap():
    values = {label: [None] * 1 for label, _period in LINES}
    values["中锋EMA144"] = [100.0]
    values["中锋EMA169"] = [110.0]
    values["红峰EMA576"] = [200.0]
    values["红峰EMA676"] = [220.0]
    assert _touched_zones(110.0, 115.0, values, 0) == ["中锋EMA144", "中锋EMA169"]
