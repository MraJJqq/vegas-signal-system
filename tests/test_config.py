from pathlib import Path

import pytest

from vegas_signal_system.config import ConfigError, load_config


def test_load_default_config():
    config = load_config(Path(__file__).parents[1] / "config" / "settings.yaml")
    enabled = [item["id"] for item in config["symbols"] if item["enabled"]]
    assert enabled[:3] == ["GOLD", "CRUDE_OIL", "BTC"]
    assert len(enabled) >= 30
    assert {"SPY", "QQQ", "NVDA", "AMD", "AVGO", "MU", "SNDK", "MSFT", "AAPL", "TSLA"} <= set(enabled)


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")
