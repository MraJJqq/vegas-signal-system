# Vegas 信号系统

独立的 Vegas 交易信号扫描项目。当前扫描池包括黄金、原油、BTC、SPY/QQQ，以及半导体、科技平台、加密相关和部分能源/工业龙头美股。**本项目只生成观察结果，不自动下单。**

## 当前规则与范围

- 4H/8H方向冲突：按规则空仓观察
- 方向一致后观察1H/2H EMA144中锋触碰
- 最新完整K线的最高价/最低价覆盖EMA144才算触碰
- 触碰只输出 `WATCH_ENTRY_CONFIRMATION`，不代表正式进场信号
- Yahoo Finance小时行情代理重采样为1H/2H/4H/8H完整K线
- 每小时自动扫描；结果CSV/JSON作为GitHub Actions构件保留14天
- 可选企业微信群机器人Markdown推送；仅推送EMA144触碰观察候选
- 单一品种数据失败不会阻断其他品种扫描
- 不自动下单、不自动管理仓位

## 美股扫描池

包含SPY、QQQ，以及NVDA、AMD、AVGO、MU、SNDK、TSM、ARM、MSFT、AAPL、AMZN、META、GOOGL、TSLA、PLTR、ORCL、NFLX、JPM、XOM、LLY、COST、COIN、MSTR、HOOD、CRWD、ANET、GE、CAT等。可在 `config/settings.yaml` 中启用/禁用或增删品种。

## 启用企业微信推送

推送使用**企业微信群机器人**Webhook，不是普通个人微信账号的直接私聊接口。

1. 在企业微信群中添加群机器人，复制Webhook地址。
2. 打开GitHub仓库的 **Settings → Secrets and variables → Actions → New repository secret**。
3. Secret名称填写 `WECHAT_WORK_WEBHOOK`，值填写完整Webhook地址。不要把Webhook写进代码、提交记录或聊天消息。
4. 打开 **Actions → Scheduled Vegas Scan → Run workflow**。
5. 首次测试时，将 `test_notification` 设为 `true` 后运行。此模式只发送测试消息，不扫描市场。
6. 测试成功后，后续每小时扫描会在存在 `WATCH_ENTRY_CONFIRMATION` 候选时推送摘要；没有候选则不推送，避免刷屏。

如果仓库Secret未配置，扫描仍可运行，只会在日志中说明通知未发送。上游行情缺失、Yahoo Finance限流或GitHub Actions配额可能影响扫描，不保证每次都成功。

## 行情源限制

Yahoo Finance是行情代理源，代码不保证与Bitget或其他经纪商图表完全一致；个别美股可能因上游数据限制而返回空数据。股票池扩展代表扩大观察范围，不代表每只股票都适合交易。方向分类和触碰后的正式确认规则仍需持续做历史数据与无未来数据审计。

## 运行方式

安装Python 3.10或更高版本：

```bash
python -m pip install -e ".[market-data]"
python -m pip install -e ".[dev]"
pytest -q
```

单次扫描：

```bash
vegas-scan --config config/settings.yaml --provider yfinance --output-dir output
```

手动测试推送（需先设置环境变量）：

```bash
export WECHAT_WORK_WEBHOOK="你的企业微信群机器人Webhook"
vegas-scan --config config/settings.yaml --test-notification
```

CSV数据格式为 `{SYMBOL_ID}_{timeframe}.csv`，必须包含 `timestamp,open,high,low,close,volume`。

任何信号逻辑更改都应经过自动测试与历史数据验证；本项目不执行交易委托。
