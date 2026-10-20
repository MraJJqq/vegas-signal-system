"""Small atomic JSON state store for V2 observation persistence and deduplication."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class StateStore:
    def __init__(self, path: str | Path = "state/vegas_v2_state.json"):
        self.path = Path(path)
        self.data: dict[str, Any] = {"observations": {}, "sent_signals": []}
        self.load()

    @staticmethod
    def observation_key(symbol: str, timeframe: str) -> str:
        return f"{symbol.upper()}|{timeframe.lower()}"

    @staticmethod
    def signal_key(symbol: str, timeframe: str, direction: str, candle_timestamp: str) -> str:
        return "|".join((symbol.upper(), timeframe.lower(), direction.lower(), str(candle_timestamp)))

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                observations = loaded.get("observations", {})
                sent = loaded.get("sent_signals", [])
                if isinstance(observations, dict) and isinstance(sent, list):
                    self.data = {"observations": observations, "sent_signals": sent}
        except (OSError, json.JSONDecodeError):
            # Fail closed: do not erase a malformed state file or assume old signals are new.
            raise RuntimeError(f"Cannot safely load V2 state file: {self.path}")

    def observation_active(self, symbol: str, timeframe: str) -> bool:
        return bool(self.data["observations"].get(self.observation_key(symbol, timeframe), False))

    def set_observation(self, symbol: str, timeframe: str, active: bool = True) -> None:
        key = self.observation_key(symbol, timeframe)
        self.data["observations"][key] = bool(active)
        self.save()

    def signal_seen(self, symbol: str, timeframe: str, direction: str, candle_timestamp: str) -> bool:
        key = self.signal_key(symbol, timeframe, direction, candle_timestamp)
        return key in set(self.data["sent_signals"])

    def mark_signal_seen(self, symbol: str, timeframe: str, direction: str, candle_timestamp: str) -> None:
        key = self.signal_key(symbol, timeframe, direction, candle_timestamp)
        seen = self.data["sent_signals"]
        if key not in seen:
            seen.append(key)
            # Bound the file while preserving recent de-duplication history.
            self.data["sent_signals"] = seen[-10000:]
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                    delete=False, newline="\n") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                temp_name = handle.name
            os.replace(temp_name, self.path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
