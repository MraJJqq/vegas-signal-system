from pathlib import Path

import pytest

from vegas_signal_system.config import ConfigError, load_config


ROOT = Path(__file__).parents[1]


def test_load_default_config():
    config = load_config(ROOT / "config" / "settings.yaml")
    enabled = [item["id"] for item in config["symbols"] if item["enabled"]]
    assert enabled == ["GOLD", "CRUDE_OIL", "BTC", "HYPE", "SNDK"]
    hype = next(item for item in config["symbols"] if item["id"] == "HYPE")
    assert hype["bitget_symbol"] == "HYPEUSDT"
    assert hype["bitget_category"] == "USDT-FUTURES"
    crude = next(item for item in config["symbols"] if item["id"] == "CRUDE_OIL")
    assert crude["bitget_symbol"] == "CLUSDT"
    assert crude["bitget_category"] == "USDT-FUTURES"


def test_load_us_stocks_futures_watchlist():
    config = load_config(ROOT / "config" / "us-stocks-settings.yaml")
    enabled = [item for item in config["symbols"] if item["enabled"]]
    assert len(enabled) == 20
    assert {"SPY", "QQQ", "NVDA", "AMD", "AVGO", "MU", "SNDK", "MSFT", "AAPL", "TSLA"} <= {
        item["id"] for item in enabled
    }
    assert all(item["bitget_symbol"].endswith("USDT") for item in enabled)
    assert all(item["bitget_category"] == "USDT-FUTURES" for item in enabled)


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")
