# VEGAS 信号系统 V5 — 规则基准

版本：V5
代码目录：`v5/`
状态：规则与代码初版已建立；尚需运行测试、行情联调和通知送达验证。
原则：未经用户明确批准，不得修改、放宽或重新解释 Vegas 判断规则。

## 1. 周期与均线
- 只使用 Bitget 4H 已收盘 K 线。
- 中锋区域：EMA144、EMA169。
- 红峰区域：EMA576、EMA676。
- 过滤线：EMA12。
- 不使用其他指标。

## 2. 独立观察
- 中锋和红峰各有独立观察状态，互不覆盖、互不取消。
- 价格 K 线范围触及相应均线区域，或收盘价位于该区域时，启动该区域观察。
- 触碰当根 K 线不发送正式信号。
- 观察状态无限期保留，直到该区域产生正式信号；不设超时。
- 每个观察区域单独判断方向：收盘价高于中锋区域上沿为 LONG，低于中锋区域下沿为 SHORT；位于中锋区域内不推断方向。
- 已启动观察后，已收盘 K 线收盘价高于 EMA12 且方向为 LONG，确认 LONG；收盘价低于 EMA12 且方向为 SHORT，确认 SHORT。
- 正式信号只使用已收盘 K 线；不得使用未收盘或未来数据。
- 中锋与红峰可分别产生信号，同一根 K 线可能同时确认两个独立观察的信号。

## 3. 扫描池与调度
- 监控 Bitget USDT 合约的美股相关扫描池；不运行 A 股扫描。
- 扫描池排除 XAUUSDT（黄金）、CLUSDT（石油）、BTCUSDT（比特币）、HYPEUSDT（HYPE），因为用户自行持续观察这些品种。
- 保留其他扫描池品种：SPYUSDT、QQQUSDT、SNDKUSDT、NVDAUSDT、AMDUSDT、AVGOUSDT、MUUSDT、TSMUSDT、MSFTUSDT、AAPLUSDT、TSLAUSDT、ARMUSDT、AMZNUSDT、METAUSDT、GOOGLUSDT、ORCLUSDT、PLTRUSDT、COINUSDT、MSTRUSDT、HOODUSDT。
- 每小时扫描一次。行情缺失、历史 K 线不足或交易所报错必须显式报告，不得静默跳过或伪造信号。
- EMA676 计算须有足够历史数据。

## 4. 通知与隔离
- 通知渠道沿用 ntfy；同一品种、同一观察类型、同一根已收盘 K 线的同一方向信号需去重。
- 代码独立放在 `v5/`。不得修改 V4、A 股历史模块或 `backtest_system/`。
- 本文件与代码初版创建不代表实时扫描、部署、通知或端到端测试已成功。
