# VEGAS AI TRADING

## 当前信号系统：V8

- V8 信号系统位于独立的 `v8/` 目录，使用 Bitget USDT 合约行情。
- 每小时扫描一次，使用已收盘的 1H K 线计算信号。
- 中锋：EMA144、EMA169；红峰：EMA576、EMA676；过滤线：EMA12。
- 仅使用用户明确确认的 Vegas 规则，不加入 RSI、MACD、布林带、ATR 或其他非 Vegas 指标。
- V8 通知通过 ntfy 发送，配置使用 GitHub Actions Secrets：`V8_NTFY_TOPIC` 和 `V8_NTFY_TOKEN`。
- V8 的观察状态与通知比较状态分别持久化；扫描数据验证失败的品种会被排除并记录原因。

## 规则保护

- 未经用户明确批准，不得修改、放宽或重新解释交易规则。
- 未经用户明确批准，不得修改推送规则。
- V7 及更早版本不作为 V8 的运行基础。
