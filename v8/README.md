# VEGAS V8 信号系统

## 正式规则
1. 行情来源：Bitget USDT 合约。
2. 自动扫描频率：每 2 小时一次。
3. 扫描周期：仅 4H。
4. 中锋：EMA144、EMA169。
5. 红峰：EMA576、EMA676。
6. 正式信号：已收盘的 4H K 线，只要最高价与最低价覆盖中锋或红峰任意一条均线值，就触发正式信号。
7. 扫描池：23 个美股合约——AAPL、MSFT、NVDA、AMZN、GOOGL、META、TSLA、ORCL、CRM、PLTR、NFLX、ADBE、IBM、AVGO、AMD、INTC、QCOM、MU、ARM、TSM、COIN、MSTR、HOOD；另加 BTCUSDT、HYPEUSDT、XAUUSDT、CLUUSDT，共 27 个品种。
8. 通知方式：ntfy。
9. 有信号时：推送正式信号详情，包括品种、触碰均线、周期和收盘价。
10. 无信号时：推送本轮扫描完成、无正式信号的通知。
11. 扫描失败时：不发送扫描完成通知。

## 配置
在 GitHub Actions Secrets 中配置：
- `V8_NTFY_TOPIC`
- `V8_NTFY_TOKEN`

密钥不写入代码。V8 使用独立的 `v8/` 目录与独立工作流。

12. 每日结果重置：以中国时间（UTC+8）为准，只将当天已收盘 4H K 线产生的信号放入当日通知；前一天信号不会进入次日通知，每天重新生成当日结果。
