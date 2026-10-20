from __future__ import annotations

import json
from io import BytesIO

import pandas as pd

from vegas_signal_system.bitget_provider import BitgetMarketDataProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_bitget_provider_loads_completed_hourly_candles(monkeypatch):
    now = pd.Timestamp.now(tz="UTC").floor("h")
    # Two completed hourly candles, newest first as Bitget commonly returns.
    rows = [
        [str(int((now - pd.Timedelta(hours=1)).timestamp() * 1000)), "102", "105", "101", "104", "12", "1200"],
        [str(int((now - pd.Timedelta(hours=2)).timestamp() * 1000)), "100", "103", "99", "102", "10", "1000"],
    ]
    monkeypatch.setattr(
        "vegas_signal_system.bitget_provider.urlopen",
        lambda request, timeout=15: FakeResponse({"code": "00000", "msg": "success", "data": rows}),
    )
    provider = BitgetMarketDataProvider([
        {"id": "BTC", "bitget_symbol": "BTCUSDT", "bitget_product_type": "USDT-FUTURES"}
    ])
    frame = provider.load("BTC", "1h")
    assert len(frame) == 2
    assert list(frame.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert frame["timestamp"].is_monotonic_increasing
    assert frame.iloc[-1]["close"] == 104


def test_bitget_provider_reports_api_errors(monkeypatch):
    monkeypatch.setattr(
        "vegas_signal_system.bitget_provider.urlopen",
        lambda request, timeout=15: FakeResponse({"code": "40034", "msg": "invalid symbol", "data": []}),
    )
    provider = BitgetMarketDataProvider([
        {"id": "BTC", "bitget_symbol": "BTCUSDT", "bitget_product_type": "USDT-FUTURES"}
    ])
    try:
        provider.load("BTC", "1h")
    except ValueError as exc:
        assert "Bitget API error" in str(exc)
    else:
        raise AssertionError("Expected API error to be surfaced")
