# VEGAS V6 SIGNAL — 核心规则

## 已确认规则
- V6 是独立重写版本，代码位于 `v6/`；不得修改或依赖 V5、监控系统或回测系统代码。
- 只使用 Vegas 三组均线：中锋、红峰、过滤线；不加入 RSI、MACD、布林带等其他指标。
- 所有判断统一使用 Bitget 的 4H 已收盘 K 线。
- 扫描任务每 2 小时运行一次。
- 中锋与红峰拥有互相独立的观察状态；触碰中锋只启动中锋观察，触碰红峰只启动红峰观察。
- 触碰只代表进入观察期，不发送正式信号通知。
- 观察期内，4H 已收盘价格位于过滤线下方为 SHORT，上方为 LONG；中锋、红峰采用相同方向定义。
- 正式信号仅在触碰之后、后续已收盘 4H K 线满足过滤线方向条件时发送。
- 每个品种当天的观察状态在中国时区日期切换时清空；第二天重新开始，不继承昨天的观察机会。
- 通知沿用用户提供的 V5 样式：黑底、标题 `VEGAS V6 SIGNAL`、白色分隔线、品种代码、`▲ LONG 🟢` / `▼ SHORT 🔴`。只有正式信号进入通知；没有正式信号不发通知。
- 通知渠道为 Server酱 Turbo 推送到微信，密钥从 GitHub Secret `SERVERCHAN_SENDKEY` 读取。

## 扫描池
- 固定资产：BTCUSDT、HYPEUSDT、XAUUSDT（黄金）、CLUSDT（原油）。
- 23 个美股候选：AAPL、MSFT、NVDA、AMZN、GOOGL、META、TSLA、AVGO、AMD、NFLX、ORCL、CRM、PLTR、INTC、QCOM、MU、ARM、TSM、COIN、MSTR、HOOD、ADBE、IBM。
- 每次扫描从 Bitget 合约列表中筛选实际正常挂牌的 USDT 合约；不伪造不存在的合约。

## 均线定义
初始实现沿用 V5 已有 Vegas 参数：中锋 EMA144/EMA169，红峰 EMA576/EMA676，过滤线 EMA12。若用户后续明确指定其他参数，才可变更。

## 运行与验证
- GitHub Actions 每 2 小时调度；也支持手动运行。
- 未配置 `SERVERCHAN_SENDKEY` 时禁止声称微信通知已送达。
- 代码测试、Bitget 联调、通知送达验证是不同的验证阶段；创建代码不等于已经完成端到端部署。
