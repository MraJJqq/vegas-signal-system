"""VEGAS V9 Bark notifier; preserves the established grouped message format."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from market_config import CORE_MARKETS as CORE_ORDER, STOCKS as STOCK_ORDER, ALLOWED_SYMBOLS

BARK_ENDPOINT = "https://api.day.app/push"
BARK_GROUP = "VEGAS V9"
BARK_TIMEOUT_SECONDS = 20
BARK_MAX_ATTEMPTS = 3
BARK_RETRY_BACKOFF_SECONDS = 1


def normalize_symbol(raw_symbol: Any) -> str:
    symbol = str(raw_symbol or "").strip().upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]
    return "CL" if symbol in {"CLU", "CL"} else symbol


def display_symbol(raw_symbol: Any) -> str:
    return normalize_symbol(raw_symbol)


def build_body(report: dict[str, Any]) -> tuple[str, list[str]]:
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
        "🔸 美股巨头\n" + grouped_lines(stocks)
        + "\n\n🔸 核心能源\n"
        + ("   ".join(f"▰ {symbol} ▰" for symbol in core) if core else "▰ No change ▰")
    )
    return body, stocks + core


def load_report(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as file:
        report = json.load(file)
    if not isinstance(report, dict):
        raise ValueError("Scan report must be a JSON object.")
    if not isinstance(report.get("signals", []), list):
        raise ValueError("The scan report 'signals' field must be a list.")
    return report


def _read_bark_response(response_body: str) -> None:
    if not response_body.strip():
        return
    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bark returned an invalid JSON response.") from exc
    if isinstance(result, dict) and "code" in result and result["code"] not in (200, "200"):
        raise RuntimeError(f"Bark rejected notification (code={result['code']}).")


def post_bark(payload: dict[str, Any]) -> None:
    request = urllib.request.Request(
        BARK_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    for attempt in range(1, BARK_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=BARK_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Bark HTTP {response.status}.")
            _read_bark_response(response_body)
            return
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == BARK_MAX_ATTEMPTS:
                raise RuntimeError(f"Bark HTTP {exc.code}; notification was not accepted.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == BARK_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Bark request failed after {attempt} attempts ({type(exc).__name__})."
                ) from exc

        delay = BARK_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
        print(f"WARNING: Bark request attempt {attempt} failed; retrying in {delay}s.", file=sys.stderr)
        time.sleep(delay)


def send_notification(report_path: str) -> int:
    bark_key = os.environ.get("V9_BARK_KEY", "").strip()
    if not bark_key:
        print("ERROR: repository secret V9_BARK_KEY is empty or missing.", file=sys.stderr)
        return 1

    try:
        report = load_report(report_path)
        body, symbols = build_body(report)
        test_mode = os.environ.get("V9_NOTIFICATION_TEST_MODE", "").strip() == "1"
        if test_mode:
            body = "【测试推送】\n" + body
        post_bark({
            "device_key": bark_key,
            "body": body,
            "group": BARK_GROUP,
            "level": "active",
        })
    except (OSError, ValueError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Bark API accepted notification; test_mode={test_mode}; "
        f"symbols={', '.join(symbols) if symbols else 'No change'}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
