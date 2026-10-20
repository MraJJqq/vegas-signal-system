# Vegas 信号系统

独立的 Vegas 交易信号扫描项目，首批观察品种为黄金、原油和 BTC。**本项目只生成观察结果，不自动下单。**

## 当前状态

已搭建第一版 Python 项目骨架：

- YAML 配置：品种、时间周期和指标参数可配置
- OHLCV 数据校验、指标计算和基础方向分类
- 4H/8H 方向冲突过滤的基线逻辑
- 1H/2H 进场观察框架
- CSV 行情输入、CSV/JSON 扫描结果输出
- 可选 Yahoo Finance 小时行情适配器，并重采样为 1H/2H/4H/8H 完整 K 线
- GitHub Actions 每小时定时扫描工作流（结果以构件保存 14 天）
- 自动单元测试和 CI 工作流

**重要限制：** 已加入可选 Yahoo Finance 数据适配器和每小时自动扫描工作流，但它属于行情代理源，不保证与 Bitget 或你的经纪商图表完全一致，也可能遇到数据缺失、延迟或服务限流。方向分类仍是开发基线，正式进场触发条件尚未全部定版，因此扫描结果仅用于观察，不是完整的正式 Vegas 信号。缺少数据或条件不完整时，不会产生正式进场信号。

## 目录

- `config/settings.yaml`：项目配置
- `src/vegas_signal_system/`：核心代码
- `data/sample/`：本地 CSV 数据格式说明
- `tests/`：单元测试
- `.github/workflows/tests.yml`：自动测试
- `.github/workflows/scan.yml`：每小时自动扫描；也可在 GitHub Actions 页面手动运行

## 环境与安装

建议使用 Python 3.10 或更高版本。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
pytest
```

Windows PowerShell 激活虚拟环境可用：

```powershell
.venv\Scripts\Activate.ps1
```

## 行情 CSV 格式

每个品种、每个周期一个文件，文件名格式：

```text
{SYMBOL_ID}_{timeframe}.csv
```

例如：`GOLD_4h.csv`、`GOLD_8h.csv`、`GOLD_1h.csv`、`GOLD_2h.csv`。

必须包含列：`timestamp,open,high,low,close,volume`。时间戳应可解析，价格与成交量必须为数字。数据源的品种代码映射需要按实际供应商核对。

## 运行扫描

```bash
vegas-scan --config config/settings.yaml
```

可选：用 Yahoo Finance 代理行情运行单次扫描（需要安装可选依赖）：

```bash
python -m pip install -e ".[market-data]"
vegas-scan --config config/settings.yaml --provider yfinance --output-dir output
```

GitHub Actions 已配置每小时自动扫描。打开仓库的 **Actions → Scheduled Vegas Scan** 可查看运行结果；每次运行会保存 CSV/JSON 结果和日志为构件，保留 14 天。定时任务受 GitHub Actions 配额、上游行情源可用性和限流影响，不保证每次都成功。该任务不会自动发送手机通知，也不会自动下单。

也可以指定输入和输出目录：

```bash
vegas-scan --data-dir data/sample --output-dir output
```

结果会输出为带时间戳的 CSV 和 JSON 文件。没有对应行情文件时，系统会输出数据不可用状态，而不是伪造信号。

## 后续开发顺序

1. 接入并核对真实行情数据源及品种代码
2. 固化完整 Vegas 方向、触碰、信号与反转规则
3. 补齐历史数据测试、无未来数据审计和结果复核
4. 验证稳定后再接入微信通知

任何信号逻辑的更改都应经过测试与历史数据验证；本项目不执行交易委托。
