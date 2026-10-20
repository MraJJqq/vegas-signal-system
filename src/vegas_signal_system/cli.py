from __future__ import annotations

import argparse

from .config import load_config
from .notifications import notify_observations, send_test_notification
from .scanner import run_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Vegas Signal System — scan observations only; no order execution.")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to YAML config")
    parser.add_argument("--data-dir", default=None, help="CSV directory containing SYMBOL_TIMEFRAME.csv files")
    parser.add_argument("--output-dir", default=None, help="Directory for scan result files")
    parser.add_argument("--provider", choices=["csv", "yfinance"], default=None, help="Override provider configured in YAML")
    parser.add_argument("--test-notification", action="store_true", help="Send a test message through the configured notification channel")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.provider:
        config.setdefault("market_data", {})["provider"] = args.provider
    notification_settings = config.get("notifications", {})
    if args.test_notification:
        print(send_test_notification(notification_settings))
        return
    results = run_scan(config, data_dir=args.data_dir, output_dir=args.output_dir)
    if results.empty:
        print("No enabled symbols configured.")
    else:
        print(results.to_string(index=False))
    print(notify_observations(results, notification_settings))
    print("\nScan complete. Results are observations only; no orders were placed.")


if __name__ == "__main__":
    main()
