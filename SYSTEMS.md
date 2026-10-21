# VEGAS 系统命名与目录规范

## 保留的正式组件

- **V1：交易/回测系统**：`backtest_system/`
- **V5：信号系统**：`v5/`
- **监控系统**：`system_monitor/`（监控说明与配置归属；实际运行以对应 workflow 为准）
- **推送机制**：V5 内的 `v5/notification_digest_v5.py`，通过 ntfy 发送 V5 通知
- **必要自动化**：V1 测试与黄金回测、V5 扫描、Bitget 连接验证。

## 隔离与规则保护

1. V1 与 V5 的代码和运行流程必须保持隔离。
2. 未经用户明确批准，不得修改、放宽、替代或重新解释已确认的 Vegas 规则。
3. 仓库工作目录只保留 V1、V5、监控系统和推送机制，以及运行它们必需的文档、测试和 workflow。
4. 旧版本目录及 A 股扫描代码/workflow 不属于当前正式组件，不得重新添加，除非用户明确要求。
5. 文档中提及的组件不代表其已成功部署；运行状态以真实 GitHub Actions 记录和推送结果为准。
6. **V5 升级保护：推送机制是 V5 的正式组成部分。** 后续升级 V5 时必须保留 `v5/notification_digest_v5.py` 及其 ntfy 去重、摘要和发送能力；未经用户明确批准，不得删除、替换或绕过它。
7. GitHub Actions 的工作流文件必须位于 `.github/workflows/v5-manual-scan.yml`，因为 GitHub 要求工作流放在该目录；它是 V5 的运行入口，必须继续调用 `v5/run_v5_hourly.py` 并配置 `NTFY_TOPIC` 和可选的 `NTFY_BASE_URL`。升级时必须一并检查调用链，不能只升级扫描代码而破坏推送。

## 调度约定

- V5 扫描的触发方式和频率以 `.github/workflows/v5-manual-scan.yml` 为准。
- V1 黄金数据下载、回测和测试由对应 V1 workflow 管理。
- 监控与通知是否实际运行，必须检查对应 workflow 和运行日志，不以目录或文档存在作为成功依据。
