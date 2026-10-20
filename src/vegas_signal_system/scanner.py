from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .data import CsvMarketDataProvider
from .bitget_provider import BitgetMarketDataProvider
from .rules import scan_symbol
from .notifications import notify_observations


def build_provider(config: dict, data_dir: str | Path | None = None):
    settings = config.get("market_data", {})
    provider_name = str(settings.get("provider", "csv")).lower()
    if provider_name == "csv":
        return CsvMarketDataProvider(data_dir or config.get("app", {}).get("csv_data_dir", "data/sample"))
    if provider_name == "bitget":
        symbols = [dict(item) for item in config.get("symbols", [])]
        for item in symbols:
            if str(item.get("id", "")).upper() == "BTC" and not item.get("bitget_symbol"):
                item["bitget_symbol"] = "BTCUSDT"
                item["bitget_product_type"] = "USDT-FUTURES"
        return BitgetMarketDataProvider(
            symbols,
            history_limit=int(settings.get("history_limit", 200)),
        )
    raise ValueError(f"Unsupported market data provider: {provider_name}")


def run_scan(config: dict, data_dir: str | Path | None = None, output_dir: str | Path | None = None) -> pd.DataFrame:
    output_dir = Path(output_dir or config.get("app", {}).get("output_dir", "output"))
    provider = build_provider(config, data_dir=data_dir)
    observations = []
    for symbol in config.get("symbols", []):
        if not symbol.get("enabled", False):
            continue
        try:
            observations.append(scan_symbol(symbol, provider, config).to_dict())
        except Exception as exc:  # isolate one symbol's failure from the rest of the scan
            observations.append({
                "symbol_id": str(symbol.get("id", "UNKNOWN")),
                "symbol_name": str(symbol.get("name", "Unknown")),
                "timestamp": "",
                "status": "SCAN_ERROR",
                "direction_4h": "unavailable",
                "direction_8h": "unavailable",
                "entry_timeframe": None,
                "close": None,
                "message": f"扫描失败：{type(exc).__name__}: {exc}",
            })
    result = pd.DataFrame(observations)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result.to_csv(output_dir / f"scan_{stamp}.csv", index=False, encoding="utf-8-sig")
    result.to_json(output_dir / f"scan_{stamp}.json", orient="records", force_ascii=False, indent=2)
    notification_settings = config.get("notifications", {})
    try:
        print(notify_observations(result, notification_settings))
    except Exception as exc:
        # Notification failures must not erase scan results or hide the scan itself.
        print(f"ntfy 通知发送失败：{type(exc).__name__}: {exc}")
    return result
