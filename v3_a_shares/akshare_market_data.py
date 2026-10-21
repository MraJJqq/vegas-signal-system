"""A-share historical-data adapter for the V3 signal engine.

BaoStock is the primary historical 60-minute provider. This module remains
isolated from the existing Bitget V3 adapter and does not change Vegas rules.

The provider's 60-minute bars are aggregated into one four-trading-hour
session candle per trading day (09:30-11:30 plus 13:00-15:00). This is
intentional for the selected A-share 4H scan setting: lunch break is not
counted as trading time. The output is not a conventional 4-hour wall-clock
bar. Every symbol must have enough valid history for EMA676 before signals
can be evaluated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MAIN_BOARD_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")
REQUIRED_EMA_HISTORY = 676
REQUIRED_60M_BARS_PER_SESSION = 4


class AShareDataError(RuntimeError):
    """Raised when A-share data is missing or fails validation."""


@dataclass(frozen=True)
class AShareCandle:
    symbol: str
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True


@dataclass(frozen=True)
class SymbolStatus:
    symbol: str
    name: str
    latest_price: float
    active: bool


def _akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise AShareDataError(
            "AKShare is not installed. Install with: pip install akshare"
        ) from exc
    return ak


def _clean_symbol(value: Any) -> str:
    symbol = str(value).strip()
    if symbol.endswith(".0"):
        symbol = symbol[:-2]
    return symbol.zfill(6)


def is_shenzhen_shanghai_main_board(symbol: str) -> bool:
    """Return True for the selected Shanghai/Shenzhen main-board prefixes."""
    code = _clean_symbol(symbol)
    return code.startswith(MAIN_BOARD_PREFIXES)


def get_main_board_universe(
    spot_df=None,
    stock_info_df=None,
) -> list[SymbolStatus]:
    """Fetch the live snapshot and return active SH/SZ main-board stocks.

    Stocks with missing, non-finite, or non-positive latest prices are
    excluded from the active universe. API omissions and malformed snapshots
    raise an error instead of being interpreted as a successful empty scan.
    """
    import math

    ak = None
    if spot_df is None or stock_info_df is None:
        ak = _akshare()
    if spot_df is None:
        spot_df = ak.stock_zh_a_spot_em()
    if stock_info_df is None:
        stock_info_df = ak.stock_info_a_code_name()

    required_spot = {"代码", "名称", "最新价"}
    if spot_df is None or not required_spot.issubset(set(spot_df.columns)):
        raise AShareDataError(
            "AKShare live snapshot missing required columns: "
            + ", ".join(sorted(required_spot))
        )
    if stock_info_df is None or not {"code", "name"}.issubset(set(stock_info_df.columns)):
        raise AShareDataError(
            "AKShare stock list missing required columns: code, name"
        )

    valid_codes = {
        _clean_symbol(code)
        for code in stock_info_df["code"].tolist()
        if is_shenzhen_shanghai_main_board(_clean_symbol(code))
    }
    result: list[SymbolStatus] = []
    for _, row in spot_df.iterrows():
        code = _clean_symbol(row["代码"])
        if code not in valid_codes or not is_shenzhen_shanghai_main_board(code):
            continue
        name = str(row["名称"]).strip()
        try:
            price = float(row["最新价"])
        except (TypeError, ValueError):
            price = float("nan")
        active = math.isfinite(price) and price > 0
        if active:
            result.append(SymbolStatus(code, name, price, True))

    if not valid_codes:
        raise AShareDataError("No Shanghai/Shenzhen main-board stocks found")
    if not result:
        raise AShareDataError(
            "Live snapshot returned no active main-board stocks; refusing to "
            "treat this as a successful scan"
        )
    return sorted(result, key=lambda item: item.symbol)


def _number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AShareDataError(f"Invalid {field}: {value!r}") from exc
    if not __import__("math").isfinite(result):
        raise AShareDataError(f"Non-finite {field}: {value!r}")
    return result


def aggregate_session_4h(
    symbol: str,
    minute_df,
    now: datetime | None = None,
) -> list[AShareCandle]:
    """Aggregate complete 60m bars into closed four-trading-hour sessions.

    Expected input columns are 时间, 开盘, 最高, 最低, 收盘, 成交量.
    Exactly four 60m bars are required per included trading date. The current
    session is excluded until after 15:05 China time.
    """
    import pandas as pd

    required = {"时间", "开盘", "最高", "最低", "收盘", "成交量"}
    if minute_df is None or not required.issubset(set(minute_df.columns)):
        raise AShareDataError(
            "60-minute data missing required columns: " + ", ".join(sorted(required))
        )
    if minute_df.empty:
        raise AShareDataError(f"{symbol}: provider returned no 60-minute history")

    frame = minute_df.copy()
    frame["时间"] = pd.to_datetime(frame["时间"], errors="coerce")
    frame = frame.dropna(subset=["时间"]).sort_values("时间")
    if frame.empty:
        raise AShareDataError(f"{symbol}: no parseable timestamps in history")

    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is not None:
        current = current.astimezone(SHANGHAI)
    include_today = current.time() >= time(15, 5)
    today = current.date()

    result: list[AShareCandle] = []
    for session_day, group in frame.groupby(frame["时间"].dt.date, sort=True):
        if session_day > today or (session_day == today and not include_today):
            continue
        # Exclude weekends/holiday-like rows with timestamps outside regular
        # continuous trading. Auction bars are not accepted as session bars.
        times = [ts.time() for ts in group["时间"]]
        expected = {time(10, 30), time(11, 30), time(14, 0), time(15, 0)}
        # Providers may label bars by start time instead of end time. Support
        # either common convention, but never accept a mixed/partial session.
        expected_start = {time(9, 30), time(10, 30), time(13, 0), time(14, 0)}
        if len(group) != REQUIRED_60M_BARS_PER_SESSION:
            continue
        actual = set(times)
        if actual != expected and actual != expected_start:
            continue

        opens = [_number(v, "open") for v in group["开盘"].tolist()]
        highs = [_number(v, "high") for v in group["最高"].tolist()]
        lows = [_number(v, "low") for v in group["最低"].tolist()]
        closes = [_number(v, "close") for v in group["收盘"].tolist()]
        volumes = [_number(v, "volume") for v in group["成交量"].tolist()]
        if any(min(o, h, l, c) <= 0 for o, h, l, c in zip(opens, highs, lows, closes)):
            continue
        if any(h < max(o, c, l) or l > min(o, c, h)
               for o, h, l, c in zip(opens, highs, lows, closes)):
            raise AShareDataError(f"{symbol} {session_day}: invalid OHLC relationship")
        result.append(AShareCandle(
            symbol=_clean_symbol(symbol),
            session_date=session_day,
            open=opens[0],
            high=max(highs),
            low=min(lows),
            close=closes[-1],
            volume=sum(max(0.0, v) for v in volumes),
            closed=True,
        ))

    # Deduplicate by date defensively and keep chronological order.
    unique = {bar.session_date: bar for bar in result}
    return [unique[day] for day in sorted(unique)]


def fetch_symbol_4h_history(
    symbol: str,
    start_date: str = "20180101",
    end_date: str | None = None,
    provider: str = "baostock",
    ak_module=None,
    now: datetime | None = None,
) -> list[AShareCandle]:
    """Fetch forward-adjusted 60m bars and aggregate to session 4H candles.

    Provider must be chosen explicitly and consistently; no silent fallback
    or mixing of sources is performed.
    """
    end_date = end_date or datetime.now(SHANGHAI).strftime("%Y-%m-%d")
    if provider == "baostock":
        try:
            import baostock as bs
        except ImportError as exc:
            raise AShareDataError(
                "BaoStock is not installed. Install with: pip install baostock"
            ) from exc
        code = _clean_symbol(symbol)
        market_code = ("sh." if code.startswith(("600", "601", "603", "605", "688")) else "sz.") + code
        login = bs.login()
        if getattr(login, "error_code", None) != "0":
            raise AShareDataError(
                f"BaoStock login failed: {getattr(login, 'error_msg', 'unknown error')}"
            )
        try:
            rs = bs.query_history_k_data_plus(
                market_code,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}",
                end_date=end_date[:10],
                frequency="60",
                adjustflag="2",
            )
            if getattr(rs, "error_code", None) != "0":
                raise AShareDataError(
                    f"BaoStock 60m query failed for {market_code}: "
                    f"{getattr(rs, 'error_msg', 'unknown error')}"
                )
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            import pandas as pd
            raw = pd.DataFrame(
                rows, columns=["date", "time", "code", "open", "high", "low",
                               "close", "volume", "amount", "adjustflag"]
            )
            if raw.empty:
                raise AShareDataError(f"BaoStock returned no 60m history for {market_code}")
            raw["时间"] = pd.to_datetime(
                raw["time"], format="%Y%m%d%H%M%S%f", errors="coerce"
            )
            df = raw.rename(columns={
                "open": "开盘", "high": "最高", "low": "最低",
                "close": "收盘", "volume": "成交量",
            })[["时间", "开盘", "最高", "最低", "收盘", "成交量"]]
        finally:
            bs.logout()
    elif provider == "eastmoney":
        # Explicit diagnostic fallback only; production defaults to BaoStock.
        ak = ak_module or _akshare()
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]} 09:30:00"
        df = ak.stock_zh_a_hist_min_em(
            symbol=_clean_symbol(symbol),
            start_date=start,
            end_date=end_date,
            period="60",
            adjust="qfq",
        )
    else:
        raise ValueError("Supported providers are 'baostock' and explicit 'eastmoney'")
    candles = aggregate_session_4h(symbol, df, now=now)
    if len(candles) < REQUIRED_EMA_HISTORY:
        raise AShareDataError(
            f"{_clean_symbol(symbol)}: only {len(candles)} complete session bars "
            f"available; V3 EMA676 requires at least {REQUIRED_EMA_HISTORY}. "
            "No signal evaluation performed."
        )
    return candles
