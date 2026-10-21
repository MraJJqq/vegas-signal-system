"""Offline tests for the isolated AKShare A-share market-data adapter."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from akshare_market_data import (
    AShareDataError,
    aggregate_session_4h,
    get_main_board_universe,
    is_shenzhen_shanghai_main_board,
)

TZ = ZoneInfo("Asia/Shanghai")


class FakeAk:
    @staticmethod
    def stock_zh_a_spot_em():
        return pd.DataFrame([
            {"代码": "000001", "名称": "平安银行", "最新价": 10.0},
            {"代码": "300750", "名称": "宁德时代", "最新价": 200.0},
            {"代码": "600000", "名称": "浦发银行", "最新价": 0},
        ])

    @staticmethod
    def stock_info_a_code_name():
        return pd.DataFrame([
            {"code": "000001", "name": "平安银行"},
            {"code": "300750", "name": "宁德时代"},
            {"code": "600000", "name": "浦发银行"},
        ])


class AkShareAdapterTests(unittest.TestCase):
    def test_main_board_prefix_filter(self):
        for code in ("000001", "001234", "002415", "003816", "600000", "601318", "603259", "605090"):
            with self.subTest(code=code):
                self.assertTrue(is_shenzhen_shanghai_main_board(code))
        for code in ("300750", "301001", "688001", "689009", "430047", "830799"):
            with self.subTest(code=code):
                self.assertFalse(is_shenzhen_shanghai_main_board(code))

    def test_universe_excludes_chinext_and_zero_price(self):
        rows = get_main_board_universe(
            spot_df=FakeAk.stock_zh_a_spot_em(),
            stock_info_df=FakeAk.stock_info_a_code_name(),
        )
        self.assertEqual([row.symbol for row in rows], ["000001"])
        self.assertEqual(rows[0].name, "平安银行")

    def test_universe_fails_closed_on_bad_snapshot(self):
        with self.assertRaises(AShareDataError):
            get_main_board_universe(
                spot_df=pd.DataFrame([{"code": "000001"}]),
                stock_info_df=FakeAk.stock_info_a_code_name(),
            )

    def test_aggregate_complete_session(self):
        df = pd.DataFrame([
            {"时间": "2026-10-20 10:30:00", "开盘": 10, "最高": 11, "最低": 9, "收盘": 10.5, "成交量": 100},
            {"时间": "2026-10-20 11:30:00", "开盘": 10.5, "最高": 12, "最低": 10, "收盘": 11, "成交量": 200},
            {"时间": "2026-10-20 14:00:00", "开盘": 11, "最高": 11.5, "最低": 10.5, "收盘": 11.2, "成交量": 150},
            {"时间": "2026-10-20 15:00:00", "开盘": 11.2, "最高": 12, "最低": 11, "收盘": 11.8, "成交量": 250},
        ])
        bars = aggregate_session_4h(
            "000001", df, now=datetime(2026, 10, 21, 9, 0, tzinfo=TZ)
        )
        self.assertEqual(len(bars), 1)
        bar = bars[0]
        self.assertEqual(bar.open, 10)
        self.assertEqual(bar.high, 12)
        self.assertEqual(bar.low, 9)
        self.assertEqual(bar.close, 11.8)
        self.assertEqual(bar.volume, 700)
        self.assertTrue(bar.closed)

    def test_incomplete_session_is_not_used(self):
        df = pd.DataFrame([
            {"时间": "2026-10-20 10:30:00", "开盘": 10, "最高": 11, "最低": 9, "收盘": 10.5, "成交量": 100},
            {"时间": "2026-10-20 11:30:00", "开盘": 10.5, "最高": 12, "最低": 10, "收盘": 11, "成交量": 200},
        ])
        bars = aggregate_session_4h(
            "000001", df, now=datetime(2026, 10, 21, 9, 0, tzinfo=TZ)
        )
        self.assertEqual(bars, [])


if __name__ == "__main__":
    unittest.main()
