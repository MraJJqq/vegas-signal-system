# VEGAS V7 信号系统

## 正式信号规则（用户最新确认）
1. 已收盘的 4H K 线价格触碰中锋或红峰，即进入观察期并立即发送正式信号通知。
2. 不再使用过滤线（EMA12）判断是否产生正式信号；过滤线不参与信号触发。
3. 当前获准扫描周期仅为 4H，不增加其他时间周期。
4. 中锋按 EMA144/EMA169 识别，红峰按 EMA576/EMA676 识别；触碰定义为 K 线最高价与最低价覆盖对应均线值。
5. 该通知表示触碰条件触发，不额外推断多空方向。

## 工程原则
- 只实现用户明确确认的 Vegas 规则，不擅自增加交易条件。
- 行情源：Bitget USDT 合约。
- 扫描频率每 2 小时一次；扫描周期仍仅为 4H。
- 每轮扫描结束通过 ntfy 通知；有正式信号时发送信号详情，无正式信号时发送无信号通知；扫描失败不发送完成通知。
- ntfy 主题通过 GitHub Actions Secret `V7_NTFY_TOPIC` 提供，不将密钥写入代码。

## 扫描池（固定 27 个品种）
- 美股（23）：AAPL、MSFT、NVDA、AMZN、GOOGL、META、TSLA、ORCL、CRM、PLTR、NFLX、ADBE、IBM、AVGO、AMD、INTC、QCOM、MU、ARM、TSM、COIN、MSTR、HOOD。
- 其他（4）：黄金 XAUUSDT、石油 CLUUSDT、BTC BTCUSDT、HYPE HYPEUSDT。
