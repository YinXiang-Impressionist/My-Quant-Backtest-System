# WorldQuant BRAIN Local Fast Backtest Engine (USA TOP3000)

[![GitHub Repo](https://img.shields.io/badge/GitHub-my--quant--backtest--system-blue.svg)](https://github.com/YinXiang-Impressionist/my-quant-backtest-system)
[![Engine Speed](https://img.shields.io/badge/Simulation-<20ms-brightgreen.svg)]()
[![Lakehouse](https://img.shields.io/badge/Dataset-3.45M%20Rows%20x%2059%20Cols-orange.svg)]()
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

针对 **WorldQuant BRAIN (USA TOP3000)** 的超快速（**<20ms**）、高保真、零未来函数、全量 59 维特征湖仓、完全离线的本地量化回测与因子初筛引擎。

配备功能完备的 **CLI 命令行工具矩阵**，支持单因子极速回测、批量初筛排行榜、全层次策略分类库与自相关性红线拦截。

---

## 🌟 核心特性与架构设计

### 1. 极速性能：Polars + Staged Pipeline AST 编译器
* **纳秒级并发向量化**：彻底摒弃低效的逐行循环，底层依托 Polars C++ 向量化引擎与多核并行计算。
* **分层阶段求值 (Staged Pipeline)**：独创 AST 语法编译器，自动将嵌套时序算子（`ts_rank`, `ts_delta` 等 `.over('ticker')`）与截面算子（`rank`, `group_neutralize` 等 `.over(['date', group])`）解耦分层计算，彻底消除 Polars 窗口上下文冲突。
* **单次回测仅需 12ms ~ 25ms**：比线上排队仿真提速数百倍，支持毫秒级高频因子调优与万级因子批量初筛。

### 2. 59 维湖仓级离线宽表 (SEC Lakehouse + PV Master Dataset)
* **345 万行 $\times$ 59 列全量离线数据集** (`data/master_backtest.parquet`)，覆盖 2018 ~ 2023 年美股 TOP3000 标的。
* **全面提取 22 大 SEC EDGAR US-GAAP 法定财务标签**：深度覆盖利润表、资产负债表、现金流量表及股份变动。
* **衍生高质量估值与运营比率**：内置 `working_capital`, `current_ratio`, `inventory_turnover`, `ebitda`, `roic`, `asset_turnover`, `ev`, `est_eps` 等。
* **多周期波动率与市场风险**：内置 `beta_last_30_days_spy`（滚动 Beta）、`volatility_20`、`volatility_60`。
* **100% 严苛 Point-in-Time (PIT) 防未来函数**：财报严格以法定正式披露日 `filed_date` 为基准进行 `join_asof` 前向对齐，并强制绑定 `delay=1`，杜绝任何前视偏差。
* **底层映射词典**：配备包含 1,652 个基本面字段与 195 个量价字段的对照表 (`data_loader/wq_sec_field_alignment.json`)。

### 3. 双向同义词映射与 4367 官方字段容错引擎
* **官方 FastExpr 命名无缝兼容**：内置全双向同义词字典，自由混用官方字段名：
  * `net_income` $\leftrightarrow$ `income` $\leftrightarrow$ `ni`
  * `operating_income` $\leftrightarrow$ `ebit` $\leftrightarrow$ `op_income`
  * `total_debt` $\leftrightarrow$ `debt`
  * `sales` $\leftrightarrow$ `revenue` $\leftrightarrow$ `turnover`
  * `cashflow_op` $\leftrightarrow$ `cfo` $\leftrightarrow$ `operating_cashflow`
  * `equity` $\leftrightarrow$ `stockholders_equity` $\leftrightarrow$ `bookvalue`
  * `shares_outstanding` $\leftrightarrow$ `shares` $\leftrightarrow$ `sharesout`
  * `beta_last_30_days_spy` $\leftrightarrow$ `beta`
  * `rd_expense` $\leftrightarrow$ `rnd_expense` 等数十种同义映射。
* **C 风格注释清洗**：原生支持 `/* 注释 */`、`//` 与 `#` 代码注释清洗。
* **长尾未披露附注智能兜底**：自动识别官方 4367 个全量字段 ID，针对极少数长尾文本附注（如 `fn_oth_...`）自动采用中性常数 `0.0` 兜底，保障因子连续回测不崩溃。
* **高保真实战 Alpha 100% 跑通**：已在离线回归测试 (`tests/test_offline_real.py`) 与样本库 (`alphas_sample.txt`) 中完成复杂因子回归测试，全部指标与官方 IS 规则严格对齐。

### 4. 1:1 复刻 WorldQuant IS 6 大红线质检体系
* **换手率 (Turnover)**：严格对齐官方双边换手定义 `0.5 * sum(|w_t - w_{t-1}|) / BookSize`，检测是否处于 1% ~ 70% 合规区间。
* **截面中性化与极值截断**：支持 `SUBINDUSTRY` 等细分行业均值中性化，默认 `truncation=0.08` 截断与多空绝对权重归一化。
* **全景指标评估**：Sharpe ($\ge 1.25$)、Fitness ($\ge 1.0$)、Margin ($\ge 10\text{ bps}$)、Returns、Max Drawdown。
* **Sub-Universe (TOP1000) 穿透检验**：针对头部千亿/百亿大市值标的独立核算 Sharpe，严防小盘股流动性虚假套利。
* **日收益自相关拦截 (Self-Correlation)**：自动与已入库因子的日度 PnL 序列计算 Pearson 相关系数，达到 `0.65` 红线即时报警拦截。

---

## 快速上手 (Quick Start)

### 1. 环境准备
推荐使用 Python 3.9+，安装核心依赖：
```bash
pip install polars numpy rich yfinance
# 或在根目录下安装为可编辑包
pip install -e .
```

### 2. 命令行常用指令 (CLI Matrix)

#### ① 字段与数据字典查询 (`fields`)
```bash
# 查看 59 个字段全景富文本表格 (含分类、字段名、中文释义、别名说明)
python -m cli fields

# 模糊搜索指定关键词 (例如利润、现金或债务)
python -m cli fields --search income
python -m cli fields --search debt
python -m cli fields --search cash

# 按资产/利润/现金流等分类筛选
python -m cli fields --category 资产

# 输出标准 JSON 格式 (供脚本或自动化流程调用)
python -m cli fields --json
```

#### ② 单因子极速回测与富文本报告 (`run`)
```bash
python -m cli run --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
```
可选参数：
* `--id "My_Alpha_01"`：指定因子标识。
* `--delay 1`：交易延迟天数（默认: 1）。
* `--neutralization SUBINDUSTRY`：中性化行业分组。
* `--truncation 0.08`：极值截断阈值（默认: 0.08）。
* `--commit`：达标后自动将日收益序列持久化入库。
* `--submit`：生成 WorldQuant FastExpr 提交单格式。
* `--json`：以 JSON 格式输出指标供上层 Agent 解析。

#### ③ 批量因子初筛排行榜与导出 (`batch`)
```bash
python -m cli batch --file alphas_sample.txt --export qualifying_alphas.csv --min-sharpe 1.25 --min-fitness 1.0
```
毫秒级遍历文件中所有因子表达式，在终端生成多维排行榜，并将所有通过 6 项红线质检的达标因子导出为 CSV。

#### ④ 因子库自相关性深度拦截 (`check-corr`)
```bash
python -m cli check-corr --expr "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)"
```
严格拦截与本地已入库因子的相关性超标因子（`>= 0.65`），防止提交重复 Alpha。

#### ⑤ 交互式向导终端 (`run.py`)
```bash
python run.py
```
调起终端可视化 Rich 菜单，提供单因子调试、经典模板调入、批量初筛、自动化假说挖掘（5 大类策略分类学）、自相关诊断、数据集探查等 8 大集成向导。

---

## 🧪 自动化测试套件 (Automated Tests)

项目配备了严格的自动化单元测试与回归套件，支持单文件直接运行或批量发现：
```bash
# 1. 运行 AST 编译器与同义词测试
python tests/test_compiler.py

# 2. 运行向量化算子数学精确度测试
python tests/test_operators.py

# 3. 运行数据管道与 PIT 规则检验
python tests/test_data_pipeline.py

# 4. 运行回测仿真器与 IS 规则测试
python tests/test_simulator.py

# 5. 运行百万行全量宽表现场回归基准测试
python tests/test_offline_real.py

# 6. 一键批量运行所有单元测试
python -m unittest discover -s tests -p "test_*.py"
```

---

## 📁 项目工程结构

```text
my-quant-backtest-system/
├── cli.py                              # 统一高性能命令行接口 (run, batch, check-corr, commit, dataset, fields)
├── run.py                              # 交互式向导脚本与策略分类树调入
├── pyproject.toml                      # PEP 621 标准项目元数据与构建配置
├── LICENSE                             # Apache 2.0 开源许可协议
├── README.md                           # 项目说明文档
├── alphas_sample.txt                   # 经典高分 Alpha 因子样例清单
├── data/
│   ├── master_backtest.parquet         # 核心离线全量宽表 (345万行 x 59列, Point-in-Time)
│   ├── ticker_subindustry_mapping.json # GICS Subindustry 行业聚类对照表
│   └── universe_top3000.json           # 美股 TOP3000 成分股全量代码池
├── data_loader/
│   ├── config.py                       # 自适应路径探测与 22 US-GAAP 财报标签注册表
│   ├── lakehouse_extractor.py          # SEC Lakehouse 高效透视抽取器 (无前视偏差)
│   ├── build_master_dataset.py         # 宽表合并构建与衍生特征向量化计算
│   └── wq_sec_field_alignment.json     # 1652个基本面+195个量价字段对齐字典
├── engine/
│   ├── expr_compiler.py                # FastExpr Staged Pipeline AST 编译器与同义词映射
│   ├── operators.py                    # 向量化算子库 (ts_*, group_*, rank, ts_zscore 等)
│   ├── simulator.py                    # 核心回测仿真器 (Turnover, PnL, Sharpe, Margin)
│   ├── correlation_checker.py          # 因子日收益自相关性检测器 (0.65 熔断拦截)
│   ├── taxonomy.py                     # 5 大类、18 个细分子类的多层级因子特征库
│   ├── visualizer.py                   # Rich 终端富文本报告与排行榜渲染器
│   └── wq_api.py                       # WorldQuant 官方接口客户端与提交单导出
└── tests/
    ├── test_compiler.py                # AST 语法树解析与同义词单元测试
    ├── test_operators.py               # 向量化算子数值正确性测试
    ├── test_simulator.py               # 回测仿真器与 IS 质检逻辑测试
    ├── test_data_pipeline.py           # 数据湖仓与特征构建管道测试
    ├── test_offline_real.py            # 离线真实高分因子真机回归测试
    └── test_benchmark.py               # 纳秒级吞吐量基准压测脚本
```

---

## 🌐 家族项目矩阵 (Ecosystem)

* 🖥️ **Web 交易终端版本**：[My Quant Backtest System GUI](https://github.com/YinXiang-Impressionist/my-quant-backtest-system-gui) —— 纯 Python 标准库驱动，内置 SVG 交互净值曲线、暗黑终端与字段词典抽屉。
* 🤖 **AI Agent 智能体技能库**：[WorldQuant Local Alpha Research Skill](https://github.com/YinXiang-Impressionist/worldquant-local-alpha-research-skill) —— 专为 Google Antigravity、Claude Code 打造的闭环自进化因子挖掘 Skill。

---

## 📄 开源许可证 (License)

本项目采用 [Apache License 2.0](LICENSE) 开源许可证。
