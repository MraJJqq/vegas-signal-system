# V1 交易系统

**正式名称：V1 交易系统**  
**简称：V1**

本目录独立保存 V1 交易/回测代码，与 V5 信号系统保持代码和运行流程隔离。名称调整不改变任何已确认的 Vegas 交易规则。

## 主程序

- `v1_trading_system.py` — V1 交易执行与风险框架
- `bitget_market_data.py` — Bitget USDT 合约历史 K 线下载器，默认黄金 `XAUUSDT`
- `run_backtest.py` — 历史回测驱动：下载行情、校验已确认信号与对应收盘 K 线、执行交易模拟并生成报告
- `test_v1_trading_system.py`、`test_run_backtest.py` — 规则、风险与回测入口测试

## 规则边界

- 按信号 K 线收盘价入场；只使用已收盘 K 线。
- 观察状态不设超时。
- 逐仓保证金预算：普通仓 10 USDT，反转试错仓 5 USDT。
- 加仓必须有新的有效 Vegas 信号，每次预算减半。
- 反转时，原趋势仓减至 20%，并建立 5 USDT 反向试错仓；试错仓不主动平仓。
- 不设置初始账户资金，不计算账户收益率。
- 小缺口合成的 K 线必须标记。
- 不添加或改写 Vegas 信号规则；信号由明确的信号规则层提供。

## 回测入口

在本目录执行：

```bash
python run_backtest.py \
  --start 2025-01-01T00:00:00Z \
  --end 2026-01-01T00:00:00Z \
  --signals confirmed_signals.json \
  --output-dir output
```

`confirmed_signals.json` 必须是已确认 Vegas 信号的 JSON 数组，每条记录包含 `symbol`、`timeframe`、`timestamp`（信号 K 线收盘时刻，含时区）、`direction`（LONG/SHORT）和 `signal_close`。驱动程序会从 Bitget 下载对应行情，核对信号时间及收盘价，验证不通过即停止，不会自行编造信号。成功后生成 `output/candles.csv` 与 `output/report.json`。

## 当前状态

- 交易执行、风险记录与回测驱动已建立。
- 规则和入口测试已加入 GitHub Actions；以实际工作流结果确认测试状态。
- **完整历史回测仍未完成验证**：必须先接入并验证符合已确认 Vegas 规则的历史信号生成层，再运行真实 GOLD 数据端到端回测。
