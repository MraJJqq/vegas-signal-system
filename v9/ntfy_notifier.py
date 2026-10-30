"""VEGAS V9 Bark notifier; preserves the established grouped message format."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.request
from typing import Any

BARK_ENDPOINT = "https://api.day.app/push"
BARK_GROUP = "VEGAS V9"
BARK_TIMEOUT_SECONDS = 20
BARK_MAX_ATTEMPTS = 3
BARK_RETRY_BACKOFF_SECONDS = 1
CORE_ORDER = ("BTC", "HYPE", "XAU", "CL")
STOCK_ORDER = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC", "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK", "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX")
ALLOWED_SYMBOLS = frozenset(CORE_ORDER + STOCK_ORDER)


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



def build_public_signal_state(report: dict[str, Any]) -> dict[str, Any]:
    """Build the webpage signal list from exactly the symbols shown in Bark."""
    _, symbols = build_body(report)
    tz = timezone(timedelta(hours=8))
    timestamp = report.get("finished_at_utc") or report.get("started_at_utc")
    try:
        scanned_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        signal_date = scanned_at.astimezone(tz).date().isoformat()
    except (TypeError, ValueError):
        signal_date = datetime.now(tz).date().isoformat()
    return {
        "__daily_formal_signals__": {
            "date": signal_date,
            "signals": [
                {"symbol": f"{symbol}USDT", "timeframe": "2H", "formal_signal": True}
                for symbol in symbols
            ],
        }
    }


def write_public_signal_state(report: dict[str, Any]) -> None:
    path = os.environ.get("V9_PUBLIC_SIGNAL_PATH", "").strip()
    if not path:
        return
    state = build_public_signal_state(report)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")


def _report_local_date(report: dict[str, Any]) -> str:
    tz = timezone(timedelta(hours=8))
    timestamp = report.get("finished_at_utc") or report.get("started_at_utc")
    try:
        scanned_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        return scanned_at.astimezone(tz).date().isoformat()
    except (TypeError, ValueError):
        return datetime.now(tz).date().isoformat()


def notification_fingerprint(body: str, report: dict[str, Any]) -> str:
    """Track delivery state and retries; never suppress a scan notification."""
    material = f"{_report_local_date(report)}\n{body}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def load_notification_state(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as file:
            state = json.load(file)
        return state if isinstance(state, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_notification_state_for_date(path: str, fingerprint: str, signal_date: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    state = {
        "version": 1,
        "date": signal_date,
        "fingerprint": fingerprint,
        "accepted_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, path)


def save_notification_state(path: str, fingerprint: str, report: dict[str, Any]) -> None:
    save_notification_state_for_date(path, fingerprint, _report_local_date(report))


def save_pending_notification(path: str, fingerprint: str, body: str, report: dict[str, Any], symbols: list[str]) -> None:
    """Persist the latest failed notification so the next scan can retry it."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    state = {
        "version": 1,
        "date": _report_local_date(report),
        "fingerprint": fingerprint,
        "body": body,
        "symbols": symbols,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, path)


def clear_pending_notification(path: str) -> None:
    """Keep a durable empty queue marker so workflow persistence is reliable."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump({"version": 1, "pending": None}, file)
        file.write("\n")
    os.replace(temporary_path, path)


def _read_bark_response(response_body: str) -> None:
    if not response_body.strip():
        return
    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bark returned an invalid JSON response.") from exc
    if isinstance(result, dict) and "code" in result and result["code"] not in (200, "200"):
        raise RuntimeError(f"Bark rejected notification (code={result['code']}).")


def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
    """Honor Bark's Retry-After hint, with a bounded exponential fallback."""
    if retry_after:
        try:
            return min(60.0, max(0.0, float(retry_after)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
                return min(60.0, max(0.0, seconds))
            except (TypeError, ValueError, OverflowError):
                pass
    return float(BARK_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))


def post_bark(payload: dict[str, Any]) -> None:
    request = urllib.request.Request(
        BARK_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    for attempt in range(1, BARK_MAX_ATTEMPTS + 1):
        retry_after = None
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
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == BARK_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"Bark request failed after {attempt} attempts ({type(exc).__name__})."
                ) from exc

        delay = _retry_delay(attempt, retry_after)
        print(f"WARNING: Bark request attempt {attempt} failed; retrying in {delay:g}s.", file=sys.stderr)
        time.sleep(delay)



def retry_pending_notification() -> int:
    """Retry a durable Bark alert independently of the market scanner."""
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).date().isoformat()
    state_path = os.environ.get(
        "V9_BARK_STATE_PATH", "v9/.bark-notification-state.json"
    ).strip()
    pending_path = os.environ.get(
        "V9_BARK_PENDING_PATH",
        os.path.join(os.path.dirname(state_path), ".bark-pending-notification-state.json"),
    ).strip()
    try:
        pending = load_notification_state(pending_path)
        if not pending.get("fingerprint"):
            print("No pending Bark notification; nothing to retry.")
            return 0
        if pending.get("date") != today:
            clear_pending_notification(pending_path)
            print("Discarded stale pending Bark notification from a previous Beijing day.")
            return 0
        body = pending.get("body")
        if not isinstance(body, str) or not body:
            raise ValueError("Pending Bark notification has no valid message body.")
        bark_key = os.environ.get("V9_BARK_KEY", "").strip()
        if not bark_key:
            raise RuntimeError("repository secret V9_BARK_KEY is empty or missing.")
        post_bark({
            "device_key": bark_key,
            "body": body,
            "group": BARK_GROUP,
            "level": "active",
        })
        save_notification_state_for_date(
            state_path, pending["fingerprint"], pending["date"]
        )
        clear_pending_notification(pending_path)
        print(
            "Pending Bark notification accepted by API; "
            f"symbols={', '.join(pending.get('symbols', [])) or 'No change'}."
        )
        return 0
    except (OSError, ValueError, urllib.error.URLError, TimeoutError, RuntimeError, KeyError) as exc:
        print(f"ERROR: Bark pending retry failed: {exc}", file=sys.stderr)
        return 1


def send_notification(report_path: str) -> int:
    try:
        report = load_report(report_path)
        body, symbols = build_body(report)
        # Build the Octopus mirror independently of Bark delivery success.
        write_public_signal_state(report)
        bark_key = os.environ.get("V9_BARK_KEY", "").strip()
        test_mode = os.environ.get("V9_NOTIFICATION_TEST_MODE", "").strip() == "1"
        if test_mode:
            body = "【测试推送】\n" + body
        state_path = os.environ.get(
            "V9_BARK_STATE_PATH", "v9/.bark-notification-state.json"
        ).strip()
        pending_path = os.environ.get(
            "V9_BARK_PENDING_PATH",
            os.path.join(os.path.dirname(state_path), ".bark-pending-notification-state.json"),
        ).strip()
        fingerprint = notification_fingerprint(body, report)
        signal_date = _report_local_date(report)
        previous_state = load_notification_state(state_path)
        pending = load_notification_state(pending_path) if not test_mode else {}

        # Retry an earlier failed alert before processing newer scan content.
        # This preserves real signal events instead of silently replacing them.
        if not test_mode and pending.get("fingerprint"):
            if pending.get("date") == signal_date and pending.get("fingerprint") != fingerprint:
                if not bark_key:
                    raise RuntimeError("repository secret V9_BARK_KEY is empty or missing.")
                post_bark({
                    "device_key": bark_key,
                    "body": pending.get("body", ""),
                    "group": BARK_GROUP,
                    "level": "active",
                })
                save_notification_state_for_date(
                    state_path, pending["fingerprint"], pending["date"]
                )
                clear_pending_notification(pending_path)
                previous_state = load_notification_state(state_path)
                print(
                    "Previously failed Bark notification was accepted on retry; "
                    f"symbols={', '.join(pending.get('symbols', [])) or 'No change'}."
                )
            elif pending.get("date") != signal_date:
                # Do not send stale alerts across Beijing calendar days.
                clear_pending_notification(pending_path)

        # Every scheduled scan must notify, even when today's cumulative
        # signal list is unchanged. The fingerprint is retained for delivery
        # state and retry tracking, not used to suppress hourly notifications.

        if not bark_key:
            if not test_mode:
                save_pending_notification(pending_path, fingerprint, body, report, symbols)
            raise RuntimeError("repository secret V9_BARK_KEY is empty or missing.")

        if not test_mode:
            save_pending_notification(pending_path, fingerprint, body, report, symbols)
        post_bark({
            "device_key": bark_key,
            "body": body,
            "group": BARK_GROUP,
            "level": "active",
        })
        if not test_mode:
            save_notification_state(state_path, fingerprint, report)
            clear_pending_notification(pending_path)
    except (OSError, ValueError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"ERROR: Bark notification failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Bark API accepted notification; test_mode={test_mode}; "
        f"symbols={', '.join(symbols) if symbols else 'No change'}."
    )
    return 0

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--retry-pending":
        sys.exit(retry_pending_notification())
    sys.exit(send_notification(sys.argv[1] if len(sys.argv) > 1 else "v9/scan-report.json"))
