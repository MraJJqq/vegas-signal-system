from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SignalObservation:
    symbol_id: str
    symbol_name: str
    timestamp: str
    status: str
    direction_4h: str
    direction_8h: str
    entry_timeframe: str | None
    close: float | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
