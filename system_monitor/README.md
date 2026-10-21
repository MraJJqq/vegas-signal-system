# 旧版 V4 运行监控（已停用）

V4 信号系统及其每小时扫描工作流已删除，因此原先针对 V4 的监控 workflow 也已删除，避免持续发出无效告警。

- 原监控工作流：`.github/workflows/system-monitor.yml`（已删除）。
- V5 当前已有手动扫描 workflow：`.github/workflows/v5-manual-scan.yml`。
- V5 自动扫描调度尚未在此处确认为每小时运行，因此本模块暂不监控 V5 的定时运行健康状态。
- V1 交易系统不受此次删除影响。

如后续为 V5 建立稳定的定时扫描 workflow，再按实际 workflow 名称和调度频率建立对应监控，避免把手动扫描误判为定时扫描故障。
