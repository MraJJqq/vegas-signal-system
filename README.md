# Vegas 信号系统

独立的 Vegas 交易信号扫描项目。当前扫描池包括黄金、原油、BTC、SPY/QQQ，以及半导体、科技平台、加密相关和部分能源/工业龙头美股。**本项目只生成观察结果，不自动下单。**

## 当前规则与范围

- 4H/8H方向冲突：按规则空仓观察
- 方向一致后观察1H/2H EMA144中锋触碰
- 最新完整K线的最高价/最低价覆盖EMA144才算触碰
- 触碰只输出 `WATCH_ENTRY_CONFIRMATION`，不代表正式进场信号
- Yahoo Finance小时行情代理重采样为1H/2H/4H/8H完整K线
- 每小时自动扫描；结果CSV/JSON作为GitHub Actions构件保留14天
- 个人微信通知通过 Server酱 API 发送；仅推送EMA144触碰观察候选
- 单一品种数据失败不会阻断其他品种扫描
- 不自动下单、不自动管理仓位

## 美股扫描池

包含SPY、QQQ，以及NVDA、AMD、AVGO、MU、SNDK、TSM、ARM、MSFT、AAPL、AMZN、META、GOOGL、TSLA、PLTR、ORCL、NFLX、JPM、XOM、LLY、COST、COIN、MSTR、HOOD、CRWD、ANET、GE、CAT等。可在 `config/settings.yaml` 中启用/禁用或增删品种。

## 设置个人微信推送（Server酱 Turbo）

1. 在 iPad 上打开 [Server酱官网](https://sct.ftqq.com)，用个人微信扫码登录。
2. 进入官网的「SendKey」页面，复制以 `SCT` 开头的 SendKey。不要把密钥发到聊天里，也不要提交到代码仓库。
3. 打开 [GitHub 仓库 Actions Secrets 设置页](https://github.com/MraJJqq/vegas-signal-system/settings/secrets/actions)。
4. 点击 **New repository secret**，名称准确填写 `SERVERCHAN_SENDKEY`，值粘贴刚才复制的 SendKey，再保存。
5. 打开 [GitHub Actions 工作流](https://github.com/MraJJqq/vegas-signal-system/actions/workflows/scan.yml)，点击 **Run workflow**，将 `test_notification` 设为 `true)，再运行。
6. 确认个人微信收到“Vegas信号系统推送测试”。收到后，后续每小时扫描在存在 `WATCH_ENTRY_CONFIRMATION` 候选时会推送摘要；没有候选则不推送，避免刷屏。

**需要你亲自完成的部分：** 第1步微信扫码登录并获取 SendKey，以及第4步把密钥粘贴到 GitHub Secret。出于账号与密钥安全原因，程序不会把密钥写入仓库或日志。完成这些后，GitHub Actions 可自动扫描和推送。

如果仓库Secret未配置，扫描仍可运行，只会在日志中说明通知未发送。Server酱免费会员官方文档注明每天最多5条；额度或上游服务异常可能影响推送。

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
export SERVERCHAN_SENDKEY="你的SendKey"
vegas-scan --config config/settings.yaml --test-notification
```

CSV数据格式为 `{SYMBOL_ID}_{timeframe}.csv`，必须包含 `timestamp,open,high,low,close,volume`。

任何信号逻辑更改都应经过自动测试与历史数据验证；本项目不执行交易委托。
