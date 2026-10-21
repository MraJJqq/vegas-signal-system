# VEGAS AI TRADING

仓库只保留当前正式组件：

- **V1 交易/回测系统**：`backtest_system/`
- **V5 信号系统**：`v5/`
- **监控系统说明与后续监控配置**：`system_monitor/`
- **推送机制**：V5 内的 `v5/notification_digest_v5.py`，通过 ntfy 发送通知
- **必要的 GitHub Actions**：V1 测试/黄金回测、V5 扫描，以及必要的连接验证工作流

## 规则保护

- V1 与 V5 代码和运行流程隔离。
- 未经用户明确批准，不得修改、放宽、替代或重新解释已确认的 Vegas 规则。
- V5 规则基准：`v5/VEGAS_SIGNAL_SYSTEM_V5.md`。
- V1 说明：`backtest_system/README.md`。
- 系统命名与状态：`SYSTEMS.md`。

## 当前状态说明

- V5 通知渠道为 ntfy；每次发送是否成功必须以实际运行日志为准。
- V5 扫描调度及运行状态以 GitHub Actions 配置和运行记录为准。
- V1 的端到端回测结果必须以实际数据和真实运行输出为准。
- `system_monitor/` 当前保留监控说明；监控是否实际运行以对应 workflow 是否存在及运行记录为准。

## 保留的工作流

- V5 扫描：`.github/workflows/v5-manual-scan.yml`
- V1 测试：`.github/workflows/test-v1.yml`
- V1 黄金数据/回测：`.github/workflows/download-v1-gold.yml`、`.github/workflows/run-v1-gold-backtest.yml`
- Bitget 行情连接验证：`.github/workflows/verify-bitget-connection.yml`

其他旧版本目录和 A 股扫描组件已清理。