# WorldQuant BRAIN Local Fast Backtest Engine (USA TOP3000)

针对 **WorldQuant BRAIN (USA TOP3000)** 的超快速（**<20ms**）、高保真、零未来函数、全量 59 维特征湖仓、完全离线的本地量化回测与因子初筛引擎。

配备功能完备的 **CLI 命令行工具矩阵**，并提供可独立部署的轻量化暗黑风格 **Web GUI** 交易终端。

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
* **C 风格注释清理**：原生支持 `/* 注释 */`、`//` 与 `#` 代码注释清洗。
* **长尾未披露附注智能兜底**：自动识别官方 4367 个全量字段 ID，针对极少数长尾文本附注（如 `fn_oth_...`）自动采用中性常数 `0.0` 兜底，保障因子连续回测不崩溃。
* **84 个真实实战 Alpha 100% 跑通**：已在真实实战因子库 (`tests/test_real_alphas.py`) 中完成 84 个复杂因子的回归测试，通过率 100%。

### 4. 1:1 复刻 WorldQuant IS 6 大红线质检体系
* **换手率 (Turnover)**：严格对齐官方双边换手定义 `0.5 * sum(|w_t - w_{t-1}|) / BookSize`，检测是否处于 1% ~ 70% 合规区间。
* **截面中性化与极值截断**：支持 `SUBINDUSTRY` 等细分行业均值中性化，默认 `truncation=0.08` 截断与多空绝对权重归一化。
* **全景指标评估**：Sharpe ($\ge 1.25$)、Fitness ($\ge 1.0$)、Margin ($\ge 10\text{ bps}$)、Returns、Max Drawdown。
* **Sub-Universe (TOP1000) 穿透检验**：针对头部千亿/百亿大市值标的独立核算 Sharpe，严防小盘股流动性虚假套利。
* **日收益自相关拦截 (Self-Correlation)**：自动与已入库因子的日度 PnL 序列计算 Pearson 相关系数，达到 `0.65` 红线即时报警拦截。

---

## 快速上手 (Quick Start)

### 1. 环境准备
推荐使用 Python 3.10+，安装核心依赖：
```bash
pip install polars numpy rich yfinance
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
python -m cli check-corr --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
```
自动与本地已提交因子库对比日收益序列，输出详细相关系数表格，若 $\ge 0.65$ 自动熔断拦截。

#### ⑤ 因子入库持久化 (`commit`)
```bash
python -m cli commit --expr "group_rank(ts_rank(fcf / cap, 60), subindustry)" --id "Alpha_FCF_Yield"
```

#### ⑥ 离线数据集查看与构建 (`dataset`)
```bash
# 查看离线宽表样本量、标的数、时间跨度与所有字段
python -m cli dataset --info

# 重新从 SEC Lakehouse 构建全量 Parquet 宽表
python -m cli dataset --build
```

---

## 📊 支持字段全景表 (59 核心字段分类)

| 分类 | 核心字段（原生列名 / 自动支持的同义词别名） | 经济学含义与量化用途 |
| :--- | :--- | :--- |
| **基础价量 (PV)** | `close`, `open`, `high`, `low`, `volume`, `vwap`, `returns`, `cap`, `adv20`, `shares_outstanding` (`shares`, `sharesout`) | 官方价格、开高低收、量价微观结构与流动性指标 |
| **资产负债表 - 资产类** | `assets` (`total_assets`), `assets_curr`, `cash` (`cash_and_equivalents`), `cash_st`, `receivable`, `inventory`, `ppent` (`ppe`), `goodwill`, `intangible_assets` | 规模基准、营运资本、资产重估、应计盈余与商誉风险 |
| **资产负债表 - 负债与权益** | `liabilities` (`total_liabilities`), `liabilities_curr`, `total_debt` (`debt`), `debt_st`, `accounts_payable` (`ap`), `equity` (`stockholders_equity`, `bookvalue`), `retained_earnings` | 杠杆率、短期偿债压力、商业信用溢价与股东权益 |
| **利润表** | `sales` (`revenues`, `turnover`), `cogs`, `gross_profit` (`gp`), `operating_income` (`ebit`), `net_income` (`income`, `ni`), `interest_expense`, `rd_expense` (`rnd_expense`), `sga_expense`, `income_tax` | 营收增长、毛利率、核心 EBIT 造血能力、研发投入与费用控制 |
| **现金流量表** | `cashflow_op` (`cfo`), `capex`, `fcf`, `cashflow_invst`, `cashflow_fin`, `cashflow_dividends` (`dividends`), `depreciation` (`depr`), `value_of_shares_reacquired_during_period` | 经营现金流真金白银、资本支出、自由现金流、分红与股票回购 |
| **财务比率与估值** | `working_capital` (`nwc`), `current_ratio` (`cr`), `inventory_turnover`, `ebitda`, `roic`, `asset_turnover`, `ev` (`enterprise_value`), `est_eps` | 净营运资本、巴菲特 ROIC 护城河、杜邦分析、企业价值与预期修正 |
| **风险模型与波动率** | `beta_last_30_days_spy` (`beta`), `volatility_20`, `volatility_60` | 相对标普 500 的 30 日滚动 Beta、短周期与中周期已实现年化波动率 |
| **截面与分组标识** | `ticker`, `date`, `filed_date`, `subindustry`, `is_top1000` | 标的代码、时间戳、财报法定披露日、GICS 中性化分组与大盘标记 |

> 完整中英文映射、SEC XBRL 标签对照及经典因子公式请查阅 [fields_summary.md](skills/wq-local-alpha-engine/references/fields_summary.md)。

---

## 🧪 自动化测试与质量保障

项目配备了严格的自动化单元测试与回归套件：
```bash
# 运行单元测试套件
python -m unittest discover -s tests -p "test_*.py"

# 运行用户真实账户 84 个 Alpha 全量回归测试
python tests/test_real_alphas.py
```

**测试覆盖矩阵**：
1. **数据管道与 PIT 规则**：验证财报数据前向对齐无未来函数；
2. **向量化算子库**：测试 `ts_*` 时序算子与 `group_*` 截面算子的数学精确度；
3. **AST 编译器与同义词 Fallback**：测试双向别名自动替换与注释清洗；
4. **回测仿真器**：验证换手率、中性化、极值截断、Sub-universe 穿透及自相关性熔断机制；
5. **真实因子压测**：84 个实战复杂因子 **100% 跑通，0 异常**。

---

## 📁 项目工程结构

```text
├── cli.py                              # 统一命令行接口 (run, batch, check-corr, commit, dataset, fields)
├── run.py                              # 交互式向导脚本与精选因子模板
├── data/
│   ├── master_backtest.parquet         # 核心离线全量宽表 (345万行 x 59列)
│   └── committed_alphas.json           # 本地已入库因子的日收益序列与元数据
├── data_loader/
│   ├── config.py                       # 路径配置与 22 US-GAAP 财报标签注册表
│   ├── lakehouse_extractor.py          # SEC Lakehouse 高效透视抽取器
│   ├── build_master_dataset.py         # 宽表合并构建与衍生特征计算
│   └── wq_sec_field_alignment.json     # 1652个基本面+195个量价字段对齐字典
├── engine/
│   ├── expr_compiler.py                # FastExpr Staged Pipeline AST 编译器与同义词映射
│   ├── operators.py                    # 向量化算子库 (ts_*, group_*, rank, ts_zscore 等)
│   ├── simulator.py                    # 核心回测仿真器 (Turnover, PnL, Sharpe, Margin)
│   ├── correlation_checker.py          # 因子自相关性检测器 (0.65 熔断机制)
│   ├── visualizer.py                   # Rich 终端富文本报告与排行榜渲染器
│   └── wq_api.py                       # WorldQuant 官方接口客户端与提交单导出
├── skills/wq-local-alpha-engine/
│   ├── SKILL.md                        # 本地量化 Agent 自动化操作指引
│   └── references/fields_summary.md    # 59 个字段与 SEC 标签对照速查手册
└── tests/
    ├── test_engine.py                  # 核心功能单元测试套件
    └── test_real_alphas.py             # 84 个用户真实 Alpha 因子全量回归压测套件
```

---

## 📄 License
MIT License.
