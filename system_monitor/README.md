# V4 运行状态监控

本模块监控 **V4 信号系统** 的 GitHub Actions 每小时扫描工作流，不修改 V4 信号判断、Vegas 规则或 V1 交易系统代码。

- 每 3 天检查一次 V4 扫描工作流最近运行状态，也支持手动触发。
- 如果找不到 V4 扫描记录、最近一次扫描失败、运行超过 90 分钟仍未完成，或超过 90 分钟没有新的扫描运行，则通过 ntfy 发出告警。
- 监控 workflow：`.github/workflows/system-monitor.yml`。
- 被监控的扫描 workflow：`.github/workflows/v4-hourly-scan.yml`，名称为 `Vegas V4 Hourly Market Scan`。
- ntfy topic 从 GitHub Actions secret `NTFY_TOPIC` 读取；另需配置 repository variable `NTFY_BASE_URL`（可选，默认 `https://ntfy.sh`）。
- 本监控反映的是 GitHub Actions 扫描工作流健康状态，不等于独立验证手机端每条 ntfy 通知均已送达。

## 配置

在仓库 Settings → Secrets and variables → Actions 中设置：

- `NTFY_TOPIC`：已订阅的 ntfy topic 名称。
- `NTFY_BASE_URL`：可选；使用自托管 ntfy 时配置服务地址。

未配置 topic 时，监控会明确报错，不会假装告警成功。
