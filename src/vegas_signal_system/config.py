from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the project configuration is missing or invalid."""


def load_config(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Configuration root must be a YAML mapping")
    for section in ("app", "symbols", "timeframes", "indicators", "rules"):
        if section not in data:
            raise ConfigError(f"Missing required configuration section: {section}")
    if not isinstance(data["symbols"], list):
        raise ConfigError("'symbols' must be a list")
    for symbol in data["symbols"]:
        if not isinstance(symbol, dict) or not {"id", "name", "enabled"}.issubset(symbol):
            raise ConfigError("Each symbol must include id, name, and enabled")
    return data
