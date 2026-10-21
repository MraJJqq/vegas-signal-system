# V1 / V3 运行状态监控

本模块只监控 V1、V3 的 GitHub Actions 自动测试结果，不修改两个系统的交易规则或业务代码。

- 每 10 分钟检查 V1、V3 测试工作流最近是否失败。
- 发现最近 20 分钟内的失败/取消结果时，通过 ntfy 发出告警。
- ntfy topic 从 GitHub Actions secret `NTFY_TOPIC` 读取；另需配置 `NTFY_BASE_URL`（可选，默认 `https://ntfy.sh`）。
- 本监控反映的是自动测试工作流健康状态，不等于 V1/V3 已部署为持续运行的生产进程。当前 V3 扫描入口仍是单次扫描，V1 完整回测流程也尚未端到端完成。

## 配置

在仓库 Settings → Secrets and variables → Actions → New repository secret 中设置：

- `NTFY_TOPIC`: 已订阅的 ntfy topic 名称。

未配置 topic 时，监控会在 GitHub Actions 日志中明确报错，不会假装告警成功。
