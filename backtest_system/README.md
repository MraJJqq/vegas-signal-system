# V1 交易系统

**正式名称：V1 交易系统**  
**简称：V1**

本目录独立保存 V1 交易/回测代码，与 V5 信号系统保持代码和运行流程隔离。名称调整不改变任何已确认的 Vegas 交易规则。

## 主程序

- `v1_trading_system.py` — V1 交易执行与风险框架
- `bitget_market_data.py` — Bitget USDT 合约历史 K 线下载器
- `run_backtest.py` — 历史回测驱动
- `test_v1_trading_system.py`、`test_run_backtest.py` — 规则、风险与回测入口测试

## V1 已确认交易规则

1. **入场方向：** 4H 和 8H 方向必须一致。
2. **入场信号：** 1H 或 2H 回撤触及中锋 EMA144，并满足 EMA12 过滤线收盘确认。
3. **入场价格：** 信号 K 线收盘价；只使用已收盘 K 线。
4. **周期优先级：** 同一标的、同一时间出现多个有效信号时，优先更高周期。
5. **BTC 与 HYPE：** 谁先出现有效信号，谁优先。
6. **首次仓位：** 10 USDT 逐仓保证金。
7. **加仓：** 必须出现新的有效 Vegas 信号；保证金依次减半：10、5、2.5、1.25 USDT……不限次数。
8. **反转条件：** 价格收盘站上 1H 中锋 EMA144，回撤不破 1H 先锋 EMA36，随后再次收盘站上中锋。
9. **反转操作：** 原趋势仓位平掉 80%，保留 20%，反方向开立 5 USDT 保证金试仓。
10. **试仓退出：** 持有至强平或既定强制退出条件，不额外添加主动退出规则。
11. **观察时间：** 不限时间，横盘也继续观察。
12. **止盈规则：** +1R 继续持有；+2R 不主动减仓；+4R 根据结构判断，不自动平仓。
13. **风险原则：** 不扩大止损风险。简化模型忽略手续费、滑点和资金费，强平损失按对应保证金计算。
14. **指标限制：** 只使用已确认的 Vegas 规则，不添加 RSI、MACD、布林带、ATR 或其他策略指标。
15. **未定义情况：** 规则没有明确写明的，一律不处理、不执行、不推测、不主动追问；只有用户明确修改时才调整。

## 回测入口

在本目录执行：

```bash
python run_backtest.py \
  --start 2025-01-01T00:00:00Z \
  --end 2026-01-01T00:00:00Z \
  --signals confirmed_signals.json \
  --output-dir output
```

`confirmed_signals.json` 必须是已确认 Vegas 信号的 JSON 数组，每条记录包含 `symbol`、`timeframe`、`timestamp`（信号 K 线收盘时刻，含时区）、`direction`（LONG/SHORT）和 `signal_close`。回测程序应使用真实行情校验信号，不得自行编造信号。

## 当前状态

V1 的规则文档已记录上述确认内容。代码执行和完整历史盈亏回测仍须以实际测试及端到端回测结果为准；规则写入文档不代表所有执行逻辑已经实现或验证通过。

## 历史强平数据核查（2026-10-21）

**结论：当前无法可靠验证 365 天黄金模拟仓位的历史强平事件。** 本结论只描述数据可用性，不改变 V1 的交易或退出规则。

### 已核对的官方资料

- Bitget 公共合约强平历史接口：`GET /api/v3/market/liquidations`。官方文档说明只提供最近 3 天数据，且可能延迟；返回的是市场强平订单记录（如合约、方向、价格、数量、时间），不是这套回测中模拟仓位的专属强平记录。官方文档：https://www.bitget.com/docs/catalog/market/derivatives
- Bitget 合约历史订单接口：`GET /api/v2/mix/order/orders-history`，官方文档注明 API 仅支持最近 90 天；这是账户订单历史，不是任意模拟交易的强平标签。官方文档：https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade
- Bitget 合约历史持仓接口：`GET /api/v2/mix/position/history-position`，官方文档注明只查询最近 3 个月的账户持仓历史。官方文档：https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position
- Bitget 的数据导出中心可导出更久的个人账户订单、成交和持仓等记录，但这些仍是实际账户记录，不能直接证明未真实下单的历史模拟仓位何时强平。官方文档：https://www.bitget.com/legacy-docs/uta/data-download-center

### 代码检查结果

- `v1_trading_system.py` 的 `mark_liquidated(..., liquidation_verified=True)` 只在调用方提供已验证强平确认后才平仓；引擎没有自行推导强平价或根据 OHLC 猜测强平。
- `test_v1_trading_system.py` 的 `test_liquidation_requires_external_verification` 只验证未确认时拒绝平仓、显式确认后允许记账；它不验证外部强平数据源的完整性或历史覆盖率。
- `run_v1_gold_backtest.py` 没有接入强平数据适配器。现有黄金回测的 365 天窗口超出公共强平接口的 3 天保留范围。

### 阻塞原因与处理边界

缺少能覆盖整个回测窗口、并能与每一笔模拟仓位可靠对应的历史强平事件数据。市场级强平记录不能证明某笔模拟仓位被强平；K 线高低价也不能在未定义杠杆和强平价的情况下作为可靠强平确认。因此不补造强平事件、不推测杠杆或强平价，也不新增退出规则。问题三可继续核对统计与现有执行逻辑，但强平相关统计必须明确标为未验证，不能当作完整历史盈亏结果。
