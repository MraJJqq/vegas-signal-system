"""VEGAS V9 Bark notifier.

Keeps the established grouped message format and only includes formal signals.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BARK_ENDPOINT = "https://api.day.app/push"
BARK_GROUP = "VEGAS V9"
CORE_ORDER = ("BTC", "HYPE", "XAU", "CL")
STOCK_ORDER = (
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC",
    "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK",
    "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX",
)
ALLOWED_SYMBOLS = frozenset(CORE_ORDER + STOCK_ORDER)


def normalize_symbol(raw_symbol: Any) -> str:
    symbol = str(raw_symbol or "").strip().upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]
    return "CL" if symbol == "CLU" else symbol


def build_body(report: dict[str, Any]) -> tuple[str, list[str]]:
    """Build the fixed V9 notification body without directional commentary."""
    unique_symbols: set[str] = set()
    for item in report.get("signals", []):
        if not isinstance(item, dict) or item.get("formal_signal") is not True:
            continue
        symbol = normalize_symbol(item.get("symbol"))
        if symbol in ALLOWED_SYMBOLS:
            unique_symbols.add(symbol)

    stocks = [symbol for symbol in STOCK_ORDER if symbol in unique_symbols]
    core = [symbol for symbol in CORE_ORDER if symbol in unique_symbols]

    def grouped_lines(symbols: list[str]) -> str:
        if not symbols:
            return "▰ No change ▰"
        return "\n".join(
            "   ".join(f"▰ {symbol} ▰" for symbol in symbols[index:index + 3])
            for index in range(0, len(symbols), 3)
        )

    body = (
        "🔸 美股巨头\n"
        f"{grouped_lines(stocks)}\n\n"
        "🔸 核心能源\n"
        f"{'   '.join(f'▰ {symbol} ▰' for symbol in core) if core else '▰ No change ▰'}"
    )
    return body, stocks + core


def load_report(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as report_file:
        report = json.load(report_file)
    if not isinstance(report, dict):
        raise ValueError("Scan report must be a JSON object.")
    if not isinstance(report.get("signals", []), list):
        raise ValueError("The scan report 'signals' field must be a list.")
    return report


def post_bark(payload: dict[str, Any]) -> None:
    request = urllib.request.Request(
        BARK_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response_body = response.read().decode("utf-8", errors="replace")
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Bark HTTP {response.status}: {response_body}")
    if response_body.strip():
        try:
            result = json.loads(response_body)
        except json.JSONDecodeError:
            result = None
        if isinstance(result, dict) and "code" in result and result["code"] not in (200, "200"):
            raise RuntimeError(f"Bark rejected notification: {response_body}")


def send_notification(report_path: str) -> int:
    bark_key = os.environ.get("V9_BARK_KEY", "").strip()
    if not bark_key:
        print("ERROR: repository secret V9_BARK_KEY is empty or missing.", file=sys.stderr)
        return 1

    try:
        report = load_report(report_path)
        body, symbols = build_body(report)
        if os.environ.get("V9_NOTIFICATION_TEST_MODE", "").strip() == "1":
            body = "【测试推送】\n" + body

        payload = {
            "device_key": bark_key,
            "body": body,
            "group": BARK_GROUP,
            "level": "active",
        }
        post_bark(payload)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError,
            TimeoutError, RuntimeError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Bark API accepted notification; "
        f"test_mode={os.environ.get('V9_NOTIFICATION_TEST_MODE', '0') == '1'}; "
        f"symbols={', '.join(symbols) if symbols else 'No change'}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
