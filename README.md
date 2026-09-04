# WorldQuant BRAIN Local Fast Backtest Engine (USA TOP3000)

针对 **WorldQuant BRAIN (USA TOP3000)** 的超快速（**<20ms**）、高保真、零未来函数、完全离线的本地量化回测与因子初筛引擎。

---

## 核心特性

1. **极致性能 (Polars + AST)**：
   - 彻底摒弃 Python 原生行级循环与低效 Pandas，采用 Polars 向量化 C++ 引擎并发运算。
   - 独创 **Staged Pipeline AST 编译器**：将嵌套时序算子（`.over("ticker")`）与截面算子（`.over(["date", group])`）分层执行，彻底消除窗口冲突。
   - 单次回测耗时控制在 **12ms ~ 25ms**，相较线上回测排队提速数百倍。

2. **100% 离线客观数据 & 零未来函数 (Point-in-Time, PIT)**：
   - 仅使用交易所官方价量 (PV) 与美国证监会 SEC EDGAR 官方法定三张表快照 (10-K/10-Q XBRL 原件)。
   - 财报数据严格基于法定正式披露时间戳 `filed_date`，通过 `join_asof(strategy="backward", by="ticker")` 严格前向对齐，并强制绑定 `delay=1`。

3. **1:1 复刻 WorldQuant IS 质检红线体系**：
   - **换手率 (Turnover)**：严格对齐官方公式 `0.5 * sum(|w_t - w_{t-1}|) / BookSize`。
   - **截面中性化与极值截断**：`SUBINDUSTRY` 均值中性化 + `truncation=0.08` 极值截断 + 多空绝对权重归一化。
   - **多维度评估**：Sharpe (年化)、Fitness、Margin (bps)、MaxDrawdown、Returns。
   - **Sub-Universe (TOP1000) 穿透检验**：大市值股票池独立核算 Sharpe，防范小市值虚假偏倚。
   - **日收益自相关拦截 (Self-Correlation)**：因子日收益序列相关性预检（`max_corr >= 0.65` 自动熔断拦截）。

4. **开箱即用的 CLI 工具与 Rich 终端仪表盘**：
   - 炫酷富文本终端面板展示回测诊断与质检矩阵。
   - 支持单因子秒级诊断、批量因子初筛生成排行榜、导出 CSV、一键生成 WorldQuant 官方 FastExpr 提交单。

---

## 快速上手 (Quick Start)

### 1. 环境准备
推荐使用 Python 3.10+，安装核心依赖：
```bash
pip install polars numpy rich yfinance
```

### 2. 常用命令行命令

#### ① 单因子极速回测与报告生成
```bash
python -m cli run --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
```
可选参数：
- `--id "Alpha_Name"`：指定因子标识。
- `--commit`：回测通过后自动将日收益序列入库，用于后续自相关性拦截。
- `--submit`：自动生成标准提交单 JSON。

#### ② 批量因子初筛与排行榜
```bash
python -m cli batch --file alphas_sample.txt --export qualifying_alphas.csv
```
自动回测文件中所有因子表达式，按 Fitness 降序排列并在终端输出精美排行榜，达标因子导出到 CSV。

#### ③ 因子库自相关性深度拦截检测
```bash
python -m cli check-corr --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
```
自动与本地已入库的所有因子计算 Pearson 相关系数，若相关性超过 0.65 立即报警。

#### ④ 离线数据集状态查看
```bash
python -m cli dataset --info
```

#### ⑤ 本地轻量化图形界面 (WorldQuant BRAIN Web GUI)
```bash
python gui.py
# 或通过 CLI 子命令启动
python -m cli gui --port 8888
```
一键调起浏览器，在暗黑沉浸式极客界面中可视化编写表达式、实时调整 Delay/Neutralization/Decay/Truncation 等参数，秒级查看 IS 6 项红线质检报告与 PnL 累计收益矢量净值曲线。

---

## 运行自动化测试
工程自带完整单元测试与基准评测：
```bash
python -m unittest discover -s tests -p "test_*.py"
```
测试覆盖：数据管道与 PIT 规则、向量化算子库、AST 编译器与同义词 fallback、回测仿真器、TOP1000 穿透、自相关性拦截，全部 100% 通过。
