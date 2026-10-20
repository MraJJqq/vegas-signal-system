from pathlib import Path

import pytest

from vegas_signal_system.config import ConfigError, load_config


def test_load_default_config():
    config = load_config(Path(__file__).parents[1] / "config" / "settings.yaml")
    assert [item["id"] for item in config["symbols"] if item["enabled"]] == [
        "GOLD", "CRUDE_OIL", "BTC"
    ]


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")
