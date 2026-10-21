# VEGAS AI TRADING

## 当前正式决定

- **V6 项目已取消**：不继续创建、开发或部署 V6。
- **V5 是当前信号系统核心**，目录为 `v5/`；后续维护和完善以 V5 为基础。
- **V1 交易/回测系统已删除**：暂不保留旧代码；待用户整理好规则与思路后，再从头重新编写。
- **监控系统**：`system_monitor/`。
- **推送机制**：V5 内的 `v5/notification_digest_v5.py`，通过 Server酱 Turbo 推送到个人微信，属于 V5 正式组成部分。

## 规则保护

- V1 重新编写前，不保留旧版交易/回测实现作为运行基础。
- 未经用户明确批准，不得修改、放宽、替代或重新解释已确认的 Vegas 规则。
- V5 规则基准：`v5/VEGAS_SIGNAL_SYSTEM_V5.md`。
- 系统命名与状态：`SYSTEMS.md`。

## 当前状态说明

- V5 通知渠道为 Server酱 Turbo 个人微信；每次发送是否成功必须以实际运行日志为准。
- V5 扫描调度及运行状态以 GitHub Actions 配置和运行记录为准。
- `system_monitor/` 是否实际运行，以对应 workflow 和运行记录为准；不能仅凭目录或文档存在判断成功。

## 保留的工作流

- V5 扫描：`.github/workflows/v5-manual-scan.yml`
- Bitget 行情连接验证：`.github/workflows/verify-bitget-connection.yml`

其他旧版本目录和 A 股扫描组件已清理。
