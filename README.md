# Vegas Signal System V3

本仓库当前开发目标仅为 **Vegas 信号系统 V3**。V3 的唯一规则基准是 `v3/VEGAS_SIGNAL_SYSTEM_V3.md`；未经用户明确批准，不得修改、放宽、替代或重新解释规则。

## V3 文件结构

- `v3/VEGAS_SIGNAL_SYSTEM_V3.md` — 唯一规则基准
- `v3/signal_system_v3.py` — V3 信号判断程序
- `v3/test_signal_system_v3.py` — V3 自动测试
- `.github/workflows/test-v3.yml` — V3 自动测试工作流

## 固定规则摘要

- 观察周期仅限 4H、8H。
- 中锋为 EMA144、EMA169；过滤线为 EMA12。
- 价格触及中锋区域，或已收盘 K 线收盘价处于中锋区域内部时，启动观察。
- 价格在中锋上方为多方向，在中锋下方为空方向。
- 观察持续到已收盘 K 线满足 EMA12 过滤条件后，才发送正式信号。
- 观察期不限时，不因横盘自动取消。
- 不使用未收盘 K 线确认信号。
- 不擅自加入其他指标、周期或条件。

## 当前开发状态

V3 规则文件、独立判断模块和基础自动测试已建立。Bitget 实时行情接入、持续扫描和 ntfy 正式通知尚未完成；通过基础单元测试不代表系统已可自主运行或已发出真实信号。

## 本地测试

需要 Python 3.12 或兼容版本：

```bash
cd v3
python -m unittest -v test_signal_system_v3.py
```

所有规则变更必须先取得用户明确批准，并同步更新规则文件与测试。
