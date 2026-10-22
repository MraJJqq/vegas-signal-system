# VEGAS V7 信号系统

## 定位
V7 是当前唯一保留的信号系统版本，从独立的 `v7/` 目录重新开始编写，不复用 V1–V6 的实现代码。

## 工程原则
- 仅使用用户明确确认的 Vegas 规则；未经明确批准，不修改、放宽或重新解释规则。
- 不加入 RSI、MACD、布林带、ATR 或其他非 Vegas 指标。
- 行情源：Bitget USDT 合约。
- 扫描频率：每 2 小时。
- 仅正式信号通过 ntfy 推送；仅触碰中锋或红峰时不推送。
- 每日观察状态不跨日延续，次日作为新一轮观察。
- ntfy 主题通过 GitHub Actions Secret `NTFY_TOPIC` 提供，不将密钥写入代码。

## 当前状态
V7 目录已建立。正式信号判定规则须严格按用户已确认的完整规则实现；在规则未核对完成前，不自行补充交易条件。

## 最终扫描池（用户确认）

固定共 27 个品种，不得擅自增删或替换：
- 美股（23）：AAPL、MSFT、NVDA、AMZN、GOOGL、META、TSLA、ORCL、CRM、PLTR、NFLX、ADBE、IBM、AVGO、AMD、INTC、QCOM、MU、ARM、TSM、COIN、MSTR、HOOD。
- 其他（4）：黄金 XAUUSDT、石油 CLUUSDT、BTC BTCUSDT、HYPE HYPEUSDT。

扫描池以本节和用户最后确认的名单为准，不参考旧版本扫描池。
