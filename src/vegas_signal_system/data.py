from __future__ import annotations

from pathlib import Path

import pandas as pd

from .indicators import validate_ohlcv


class CsvMarketDataProvider:
    """Local CSV provider for development and repeatable tests.

    Expected path: data_dir/{symbol_id}_{timeframe}.csv, e.g. GOLD_4h.csv.
    Live exchange/broker APIs are deliberately not assumed in this scaffold.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load(self, symbol_id: str, timeframe: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol_id}_{timeframe}.csv"
        if not path.exists():
            raise FileNotFoundError(f"No market data file: {path}")
        return validate_ohlcv(pd.read_csv(path))
