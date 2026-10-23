"""Read-only validation of the fixed V9 Bitget USDT-FUTURES market pool."""
from __future__ import annotations
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.bitget.com"
PRODUCT = "USDT-FUTURES"
SYMBOLS = (
    "BTCUSDT", "HYPEUSDT", "XAUUSDT", "CLUSDT", "SNDKUSDT",
    "AAPLUSDT", "AMZNUSDT", "GOOGLUSDT", "NVDAUSDT", "JPMUSDT",
    "COINUSDT", "CRWDUSDT", "BABAUSDT", "NFLXUSDT", "UBERUSDT",
    "CATUSDT", "CEGUSDT", "CVXUSDT", "TSLAUSDT",
)

def get(path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}{path}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "VEGAS-V9-read-only-validator/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("code") != "00000":
        raise RuntimeError(f"{path}: API error: {payload!r}")
    return payload

def main() -> int:
    errors = []
    print("V9 Bitget fixed-pool validation (read-only)")
    contracts_payload = get("/api/v2/mix/market/contracts", {"productType": PRODUCT})
    contracts = {str(x.get("symbol", "")).upper(): x for x in contracts_payload.get("data", []) if isinstance(x, dict)}
    tickers_payload = get("/api/v2/mix/market/tickers", {"productType": PRODUCT})
    tickers = {str(x.get("symbol", "")).upper(): x for x in tickers_payload.get("data", []) if isinstance(x, dict)}
    now_ms = int(time.time() * 1000)
    print("symbol | contract | ticker | last price | ticker age")
    for symbol in SYMBOLS:
        contract = contracts.get(symbol)
        ticker = tickers.get(symbol)
        contract_ok = bool(contract)
        # Only accept a contract explicitly listed as normal/trading if status is supplied.
        status = str((contract or {}).get("symbolStatus", (contract or {}).get("symbolstatus", ""))).lower()
        if contract and status and status not in ("normal", "listed", "trading", "online"):
            contract_ok = False
            errors.append(f"{symbol}: unexpected contract status={status}")
        price = 0.0
        age_s = None
        try:
            price = float((ticker or {}).get("lastPr", "0"))
            ts = int((ticker or {}).get("ts", "0"))
            age_s = max(0, (now_ms - ts) // 1000) if ts else None
        except (TypeError, ValueError):
            pass
        ticker_ok = bool(ticker) and price > 0 and age_s is not None and age_s <= 300
        if not contract_ok:
            errors.append(f"{symbol}: missing from contracts endpoint")
        if not ticker_ok:
            errors.append(f"{symbol}: ticker missing/invalid/stale (price={price}, age_s={age_s})")
        print(f"{symbol} | {'PASS' if contract_ok else 'FAIL'} | {'PASS' if ticker_ok else 'FAIL'} | {price} | {age_s}")
    print(f"SUMMARY: pool={len(SYMBOLS)} contract_ok={sum(s in contracts for s in SYMBOLS)} ticker_fresh_ok={sum(1 for s in SYMBOLS if s in tickers and float(tickers[s].get('lastPr', 0) or 0) > 0 and 0 <= (now_ms-int(tickers[s].get('ts', 0) or 0))//1000 <= 300)} errors={len(errors)}")
    if errors:
        for err in errors:
            print("ERROR:", err)
        return 1
    print("PASS: all 19 symbols are listed as contracts and have fresh tickers.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
