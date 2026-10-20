# Vegas 信号系统

独立的 Vegas 交易信号扫描项目，首批观察品种为黄金、原油和 BTC。**本项目只生成观察结果，不自动下单。**

## 当前状态

已搭建第一版 Python 项目骨架：

- YAML 配置：品种、时间周期和指标参数可配置
- OHLCV 数据校验、指标计算和基础方向分类
- 4H/8H 方向冲突过滤的基线逻辑
- 1H/2H 进场观察框架
- CSV 行情输入、CSV/JSON 扫描结果输出
- 基础单元测试和 CI 工作流

**重要限制：** 目前没有连接实时行情源，也没有把所有正式进场触发条件定版。方向分类是用于搭建与测试的基线，不应视为完整的正式 Vegas 信号。缺少数据或条件不完整时，不会产生正式进场信号。

## 目录

- `config/settings.yaml`：项目配置
- `src/vegas_signal_system/`：核心代码
- `data/sample/`：本地 CSV 数据格式说明
- `tests/`：单元测试
- `.github/workflows/tests.yml`：自动测试

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
