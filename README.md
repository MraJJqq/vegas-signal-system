# Vegas 信号系统

独立的 Vegas 交易信号扫描项目。当前扫描池包括黄金、原油、BTC、SPY/QQQ，以及半导体、科技平台、加密相关和部分能源/工业龙头美股。**本项目只生成观察结果，不自动下单。**

## 当前规则与范围

- 4H/8H方向冲突：按规则空仓观察
- 方向一致后观察1H/2H EMA144中锋触碰
- 最新完整K线的最高价/最低价覆盖EMA144才算触碰
- 触碰只输出 `WATCH_ENTRY_CONFIRMATION`，不代表正式进场信号
- Yahoo Finance小时行情代理重采样为1H/2H/4H/8H完整K线
- 每小时自动扫描；结果CSV/JSON作为GitHub Actions构件保留14天
- ntfy 通知推送到 iPad/iPhone；仅推送EMA144触碰观察候选
- 单一品种数据失败不会阻断其他品种扫描
- 不自动下单、不自动管理仓位

## 美股扫描池

包含SPY、QQQ，以及NVDA、AMD、AVGO、MU、SNDK、TSM、ARM、MSFT、AAPL、AMZN、META、GOOGL、TSLA、PLTR、ORCL、NFLX、JPM、XOM、LLY、COST、COIN、MSTR、HOOD、CRWD、ANET、GE、CAT等。可在 `config/settings.yaml` 中启用/禁用或增删品种。

## 设置 ntfy 推送到 iPad

1. 在 iPad 上打开 [App Store ntfy 搜索页](https://apps.apple.com/search?term=ntfy)，安装 ntfy 官方应用。
2. 打开 App，添加/订阅一个主题（Subscribe）。
3. 使用密码管理器生成至少32位随机主题名，只使用英文字母、数字、下划线或连字符。主题名相当于密码，不要使用容易猜测的名称。
4. 打开 [GitHub 仓库 Actions Secrets 设置页](https://github.com/MraJJqq/vegas-signal-system/settings/secrets/actions)，点击 **New repository secret**，名称填 `NTFY_TOPIC`，值填主题名，保存。不要把主题名发到聊天里或提交到仓库。
5. 打开 iPad「设置 → 通知 → ntfy」，允许通知，并检查专注模式设置。
6. 打开 [GitHub Actions 工作流](https://github.com/MraJJqq/vegas-signal-system/actions/workflows/scan.yml)，点击 **Run workflow**，把 `test_notification` 设为 `true)，运行后检查 ntfy App 是否收到测试消息。

成功后，每小时扫描只会在存在 `WATCH_ENTRY_CONFIRMATION` 候选时发送一条汇总消息；没有候选则不推送。通知仅供观察，不是正式进场信号，系统不会自动下单。

默认使用公共服务 `https://ntfy.sh`。如果以后使用自己的 ntfy 服务器，可在 GitHub 仓库 Settings → Secrets and variables → Actions → Variables 中添加 `NTFY_BASE_URL`，值为 HTTPS 服务根地址。公共主题可被知道主题名的人订阅，因此必须将主题名视为密码；公共服务仍是第三方中转。即使自建服务器，iOS 即时通知也可能依赖 ntfy.sh 的上游推送基础设施。

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
export NTFY_TOPIC="你的随机主题名"
vegas-scan --config config/settings.yaml --test-notification
```

CSV数据格式为 `{SYMBOL_ID}_{timeframe}.csv`，必须包含 `timestamp,open,high,low,close,volume`。

任何信号逻辑更改都应经过自动测试与历史数据验证；本项目不执行交易委托。
