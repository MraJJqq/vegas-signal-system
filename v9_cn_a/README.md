# VEGAS V9 A股扫描系统

独立目录 `v9_cn_a/`，与美股 V9 `v9/` 分离。不得导入美股目录代码、共享状态文件、报告文件或工作流并发组。

## 扫描触发规则

- **仅允许手动运行**：GitHub Actions → `VEGAS V9 A股 Tencent Scan` → `Run workflow`。
- **禁止自动扫描**：工作流只保留 `workflow_dispatch`；不得添加 `schedule`、`push`、`pull_request` 或其他自动触发器。
- 此限制仅针对 A 股工作流，不修改美股 V9 的扫描设置。

## 扫描配置

- 行情源：腾讯公开行情接口
- 周期：1H，仅使用已收盘 K 线
- 信号规则：独立副本，保持 V9 EMA144/169、EMA576/676 观察线及 EMA12 确认规则
- 状态：`v9_cn_a/.signal-state.json`
- 报告：`v9_cn_a/scan-report.json`

初始观察池为 50 只沪深主板、创业板及科创板流动性较高的代表性股票，不代表买卖建议。腾讯公开接口可能调整；每只股票均须通过数据校验后才纳入本轮扫描。
