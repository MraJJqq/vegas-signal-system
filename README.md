# VEGAS AI TRADING — V1 交易系统与 V4 信号系统

本仓库当前的正式系统为两个相互隔离的子系统：

- **V1：交易系统** — `backtest_system/`，负责按明确的 Vegas 信号模拟入场、加仓、反转、风险记录和历史回测。
- **V4：信号系统** — `v4/`，负责读取 Bitget USDT 合约已收盘 4H 行情、按 V4 规则判断信号并通过 ntfy 通知。
- **A 股扫描模块** — `v3_a_shares/`，独立历史模块，当前暂停使用，不属于 V4。

## 命名与规则保护

- V1 与 V4 的代码和运行流程独立；不要将 V1 的回测执行逻辑混入 V4。
- Vegas 规则未经用户明确批准不得修改、放宽、替代或重新解释。
- V4 规则基准：`v4/VEGAS_SIGNAL_SYSTEM_V4.md`。
- V1 交易框架说明：`backtest_system/README.md`。
- 统一命名与运行状态：`SYSTEMS.md`。
- `v3_a_shares/` 是暂停使用的旧 A 股扫描模块；旧名称不代表当前信号系统版本。未经明确授权，不删除或重新启用该模块。

## V4 当前状态

- V4 扫描入口、Bitget 行情适配、信号判断、ntfy 摘要/去重、测试与每小时 GitHub Actions workflow 已建立。
- 已有 V4 测试和扫描 workflow 成功记录；这不等于独立确认每次手机端通知均已送达。
- 实际运行状态以最新 GitHub Actions 结果为准。

## V1 当前状态

- 已建立交易执行、风险记录与回测驱动框架。
- 完整历史回测仍需以符合已确认 Vegas 规则的历史信号生成层进行端到端验证；不得把缺少信号误称为已完成回测。
- 初始资金、收益率等统计按 V1 规则文档所列范围处理。

## 自动化工作流

- V4 测试：`.github/workflows/test-v4.yml`
- V4 每小时扫描：`.github/workflows/v4-hourly-scan.yml`
- V1 测试：`.github/workflows/test-v1.yml`
- V1 黄金数据与回测：查看 `.github/workflows/` 下以 `v1-gold` 命名的 workflow。
- A 股 workflow 仍可能存在于仓库中；A 股扫描模块当前暂停使用，需将其工作流状态与代码状态区分看待。

所有验证结论以实际工作流结果和真实回测输出为准。
