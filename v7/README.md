# VEGAS V7 信号系统

## 定位
V7 是当前保留的信号系统版本，代码位于独立的 `v7/` 目录。

## 正式信号规则（用户最新确认）
1. 价格触碰中锋或红峰后，进入持续观察状态。
2. 触碰后持续观察最近的已收盘 K 线；不设观察时间限制。
3. 最近 K 线收盘价位于过滤线一侧，即产生正式信号并通知。
4. 本仓库当前获准扫描周期仅为 4H；过滤线按现有 V7 定义使用 EMA12。不得擅自增加周期或指标。
5. 中锋对应 EMA144/EMA169，红峰对应 EMA576/EMA676；触碰定义为 K 线最高价与最低价覆盖对应均线值。

## 工程原则
- 仅使用用户明确确认的 Vegas 规则；未经明确批准，不修改、放宽或重新解释规则。
- 行情源：Bitget USDT 合约。
- 自动扫描每 2 小时运行；运行频率不代表扫描其他 K 线周期。
- 每轮扫描结束通过 ntfy 通知：有正式信号时发送信号详情，无正式信号时发送无信号通知；扫描失败不发送完成通知。
- 每日观察状态不跨日延续，次日作为新一轮观察。
- ntfy 主题通过 GitHub Actions Secret `V7_NTFY_TOPIC` 提供，不将密钥写入代码。

## 扫描池（用户确认）
固定共 27 个品种，不得擅自增删或替换：
- 美股（23）：AAPL、MSFT、NVDA、AMZN、GOOGL、META、TSLA、ORCL、CRM、PLTR、NFLX、ADBE、IBM、AVGO、AMD、INTC、QCOM、MU、ARM、TSM、COIN、MSTR、HOOD。
- 其他（4）：黄金 XAUUSDT、石油 CLUUSDT、BTC BTCUSDT、HYPE HYPEUSDT。
