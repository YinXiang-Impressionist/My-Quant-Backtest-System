---
name: wq-local-alpha-engine
description: "WorldQuant BRAIN 本地超快速 (<20ms) 离线量化回测与因子初筛引擎研发指南。基于 345 万行 x 59 维 SEC EDGAR Lakehouse 宽表、Polars C++ 并发引擎、Staged Pipeline AST 编译器以及官方 4367 字段双向同义词映射。用于：极速挖掘 Alpha、运行毫秒级回测、诊断 IS 6 项红线质检（Sharpe/Fitness/Turnover/Drawdown/Sub-Universe TOP1000）、前置拦截日收益自相关（< 0.65）、跨源杂交进化高分因子以及自动化线上提交。触发词包含：'本地极速挖因子'、'本地引擎挖因子'、'开始本地挖掘'、'用本地引擎测试因子'、'基于本地回测挖新因子'、'全自动本地挖掘流水线'、'/wq-local-alpha-engine'。"
---

# WorldQuant BRAIN 本地极速量化研发与自进化引擎 Skill

> **一句话开箱即用**：
> 在任意会话中，只需对助手说：**“开始本地极速挖因子”** 或 **“用本地引擎测试因子”**，助手便会自动挂载本项目本地离线高保真数据集（**3,458,748 行 $\times$ 59 维特征** 无前视偏差价量与 SEC EDGAR 财报宽表），在 **15ms ~ 25ms** 内完成单次回测、执行 IS 六项严格质检与自相关拦截，并在发现高分苗头时就地多轮杂交进化！

---

## 1. 核心架构与本地先行流水线 (Local-First Hybrid Pipeline)

```
用户指令 (“开始本地极速挖因子”)
  ├── 1. 挂载本地离线客观数据库 (Point-in-Time, 100% 零未来函数)
  │    └── data/master_backtest.parquet (345万行 x 59列, date >= filed_date, delay=1, TOP3000池)
  ├── 2. 候选特征生成与 AST 分层编译
  │    ├── 利用 TSExtractor 将时序算子 (.over("ticker")) 与截面算子分层解耦
  │    └── 官方 4367 字段智能双向映射 (income <-> net_income, debt <-> total_debt, ebit, etc.)
  ├── 3. 本地毫秒级回测仿真 (<20ms / 因子)
  │    ├── SUBINDUSTRY 行业截面中性化 + 0.08 极值截断 + scale(1.0)
  │    ├── 精确计算单边换手率: 0.5 * sum(|pos_t - pos_{t-1}|)
  │    └── 评估 Sharpe, Fitness, Turnover, Drawdown, Margin, Sub-Universe TOP1000
  ├── 4. 全量 WorldQuant IS 质检与动态进化决策:
  │    ├── 具备进化苗头的因子 (Sharpe > 1.0 或单边突破) ──→ 必须就地双核加权/跨源杂交进化！
  │    ├── 彻底失效因子 (Sharpe < 0 或逻辑崩塌) ──→ 抛弃，测试下一特征
  │    └── 达标因子 (Sharpe >= 1.25, Fitness >= 1.0, 全部 IS PASS) ──→ 进入第 5 步
  ├── 5. 本地因子库日收益相关性前置拦截 (< 0.65 红线):
  │    ├── 与库内【任一】已提交因子的日收益 Pearson Corr >= 0.65 ──→ 触发熔断拦截，就地变异换底仓！
  │    └── 与库内【所有】已有因子的日收益 Pearson Corr < 0.65 ──→ 允许持久化入库与线上提交！
  └── 6. 自动生成 WorldQuant 官方 FastExpr 提交单与线上联动:
       ├── 本地落盘标准 Submission Payload JSON (data/submissions/)
       └── 调用官方 API 提交线上并验证状态 status == ACTIVE (流水线永不因单个成功而终止！)
```

---

## 2. 命令行极速工具链 (CLI Reference)

工程内置统一的高性能命令行工具 `cli.py` 与辅助脚本 [run_alpha.py](./scripts/run_alpha.py)：

### 2.1 字段速查与模糊搜索 (`fields`)
```powershell
python -m cli fields --search income
python -m cli fields --category 资产
python -m cli fields --json
```
- 详见文档：[fields_summary.md](./references/fields_summary.md)

### 2.2 单因子即时诊断与回测 (`run`)
```powershell
python -m cli run --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)" --id "Alpha_ROE_Trend"
```
- **参数说明**：
  - `--commit`：回测通过后自动将该因子的日收益 PnL 序列写入已提交因子库，供后续自相关性拦截比对。
  - `--submit`：自动在 `data/submissions/` 生成标准 JSON 提交包并可直接调用线上 API。
  - `--no-corr`：跳过自相关性检测（快速测试时可用）。

### 2.3 批量因子高通量初筛与排行榜 (`batch`)
```powershell
python -m cli batch --file alphas_sample.txt --export qualifying_alphas.csv
```
- 读取因子清单文件，以每秒 50+ 个因子的吞吐量快速完成并发回测；
- 按照 **Fitness** 降序渲染美观的富文本终端排行榜；
- 自动将符合 Sharpe $\ge 1.25$ 与 Fitness $\ge 1.0$ 的优质因子导出为 CSV。

### 2.4 因子库自相关性深度扫描与拦截 (`check-corr`)
```powershell
python -m cli check-corr --expr "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)"
```
- 输出待测因子与本地已提交因子库中所有历史因子的详细 Pearson 相关系数表；
- 超过 0.65 红线自动高亮标红并告警。

### 2.5 启动图形化 Web GUI 交易终端 (`gui`)
```powershell
python gui.py
# 或
python -m cli gui --port 8888
```
- 调起暗黑极客风格终端，支持公式编辑、SVG 矢量收益曲线、**「📖 字段与算子词典」抽屉（点击直接插入代码）**。

---

## 3. WorldQuant IS 六项严格质检红线与调优手册

详细公式与背景请查阅：[is_rules.md](./references/is_rules.md)。

| 质检项 (Check Item) | 官方红线 | 物理/金融含义 | 常见未达标原因 | 针对性调优策略 |
| :--- | :--- | :--- | :--- | :--- |
| **LOW_SHARPE** | **$\ge 1.25$** | 经波动率调整后的超额收益能力 | 信号衰减过快、噪声过大、未行业中性化 | 1. 延长时序平滑窗口 `ts_rank(x, 126)` 或 `ts_decay_linear(x, 63)`<br>2. 引入双核因子互补加权 `0.5*A + 0.5*B` |
| **LOW_FITNESS** | **$\ge 1.0$** | 收益率与换手率惩罚的综合效能：$\text{Sharpe} \times \sqrt{\frac{\|\text{Ret}\|}{max(TO, 0.125)}}$ | 换手率过高（吞噬收益）或年化绝对收益不足 | 1. 增加时序衰减算子 `ts_decay_linear` 降低换手<br>2. 引入 `trade_when` 或加大时序窗口 |
| **TURNOVER** | **$1\% \sim 70\%$** | 双边/单边换手率范围 | 信号变动过于频繁（>70%）或信号完全钝化（<1%） | 1. 若换手过高：使用 `ts_decay_linear`、`ts_mean` 替换高频差分<br>2. 若换手过低：降低 lookback 周期或增加灵敏度 |
| **DRAWDOWN** | **$< 25.0\%$** | 历史最大净值回撤 | 熊市期单边暴跌、缺乏中性化对冲 | 1. 确保使用 `group_neutralize(x, "subindustry")`<br>2. 叠加防御性现金流或杠杆约束因子 |
| **SUB_UNIVERSE_TOP1000** | **$\ge 1.0$** | 大市值前 1000 标的独立 Sharpe 检验 | 仅在小微盘股生效，遭遇大票流动性陷阱 | 1. 避免使用对市值极其敏感的微小科目比率<br>2. 与大票成交量或市值加权 `x * adv20` 提升大票稳健性 |
| **SELF_CORRELATION** | **$< 0.65$** | 与库内已存在因子的日收益相关性 | 因子与已有资产思路高度同质化（同义词或微调） | 1. 跨源特征杂交（如财报质量 + 动量反转）<br>2. 改变分母基准（如除以 `assets` 改为除以 `equity` 或 `cash`） |

---

## 4. 黄金算子库与表达式构建模式

完整算子数学定义与用法详见：[operators_reference.md](./references/operators_reference.md)。

### 4.1 核心黄金结构
WorldQuant 历年实战验证表现最稳健、最高通过率的四大范式：

1. **基本面质量时序趋势 (Fundamental Quality Trend)**：
   ```python
   group_rank(ts_rank(operating_income / equity, 126), subindustry)
   ```
2. **总资产真实现金回报率 (True Cash Flow Return)**：
   ```python
   group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
   ```
3. **双核质量跨源杂交 (Dual-Core Hybridization)**：
   ```python
   0.5 * group_rank(ts_rank(operating_income / equity, 126), subindustry) + 0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry)
   ```
4. **【已验证满贯】微观反转动量 + 股票回购注销**：
   ```python
   0.6 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry) + 0.4 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)
   ```

### 4.2 算子兼容速查表
- **截面类**：`rank(x)`, `zscore(x)`, `scale(x, 1.0)`, `winsorize(x, std=4.0)`
- **分组类**：`group_rank(x, subindustry)`, `group_zscore(x, subindustry)`, `group_neutralize(x, subindustry)`
- **时序类**：`ts_rank(x, d)`, `ts_decay_linear(x, d)`, `ts_std_dev(x, d)`, `ts_corr(x, y, d)`, `ts_zscore(x, d)`, `ts_delay(x, d)`, `ts_delta(x, d)`, `ts_mean(x, d)`
- **数学与逻辑**：`if_else(cond, true_val, false_val)`, `trade_when(cond, alpha, -1)`, `signed_power(x, p)`, `log(x)`, `abs(x)`, `sign(x)`

---

## 5. 59 维核心宽表与同义词映射速查

宽表内置 59 维无前视偏差特征，完整映射表见 [fields_summary.md](./references/fields_summary.md)：

| 类别 | 原生列名 | 常用同义词别名 (自动 Fallback) | 经济学含义 |
| :--- | :--- | :--- | :--- |
| **基础价量** | `close`, `open`, `high`, `low`, `volume`, `vwap`, `returns`, `cap`, `adv20` | `shares` $\leftrightarrow$ `shares_outstanding` | 官方交易所价量、均价与市值 |
| **资产类** | `assets`, `assets_curr`, `cash`, `cash_st`, `receivable`, `inventory`, `ppent`, `goodwill`, `intangible_assets` | `total_assets`, `current_assets`, `ppe` | 资产负债表资产端、营运资产与安全垫 |
| **负债权益** | `liabilities`, `liabilities_curr`, `total_debt`, `debt_st`, `accounts_payable`, `equity`, `retained_earnings` | `debt` $\leftrightarrow$ `total_debt`, `stockholders_equity` | 杠杆率、有息负债、净资产与留存利润 |
| **利润表** | `sales`, `cogs`, `gross_profit`, `operating_income`, `net_income`, `interest_expense`, `rd_expense`, `sga_expense`, `income_tax` | `income` $\leftrightarrow$ `net_income`, `ebit` $\leftrightarrow$ `operating_income`, `revenue` | 营收增长、毛利、营业利润、底线收益与研发 |
| **现金流量表** | `cashflow_op`, `capex`, `fcf`, `cashflow_invst`, `cashflow_fin`, `cashflow_dividends`, `depreciation`, `value_of_shares_reacquired_during_period` | `cfo` $\leftrightarrow$ `cashflow_op`, `dividends`, `depr` | 经营现金造血、自由现金流、分红派息与股票回购 |
| **比率与估值** | `working_capital`, `current_ratio`, `inventory_turnover`, `ebitda`, `roic`, `asset_turnover`, `ev`, `est_eps` | `nwc`, `cr`, `enterprise_value` | 营运资本、巴菲特 ROIC 护城河、杜邦分析与企业价值 |
| **风险波动** | `beta_last_30_days_spy`, `volatility_20`, `volatility_60` | `beta`, `vol_20`, `vol_60` | 滚动 30 日系统性 Beta、20/60 日年化收益波动率 |
| **截面标识** | `ticker`, `date`, `filed_date`, `subindustry`, `is_top1000` | - | 标的代码、时间戳、法定披露日、中性化分组与大盘标记 |

---

## 6. 自主进化研发实战流程 (Prompt Execution SOP)

当用户说 **“开始本地极速挖因子”** 时，Agent 应当执行以下闭环：

1. **第 1 步：生成候选种子**：选取 3~5 个具有清晰经济学逻辑的候选表达式；
2. **第 2 步：执行高通量初筛**：直接运行 [mine_alphas.py](./scripts/mine_alphas.py) 或 `python -m cli batch`；
3. **第 3 步：见苗头即进化 (Evolve)**：若发现某因子 Sharpe $\ge 1.0$ 但其他指标未满贯，**禁止直接丢弃**，立即与正交特征（如自由现金流、股票回购或动量）加权杂交；
4. **第 4 步：自相关拦截检验**：调用 `CorrelationChecker` 验证与库内因子最大相关系数 $< 0.65$；
5. **第 5 步：入库持久化**：执行 `--commit` 写入本地已提交因子库，并生成 WorldQuant 官方 JSON 提交单！

---

## 7. Skill 自动化验证与自测工具

本 Skill 配备了一键式自检验证脚本 [test_skill.py](./scripts/test_skill.py)：
```powershell
python scripts/test_skill.py
```
- **验证范围**：
  1. 目录结构与关键文件完整性；
  2. YAML Frontmatter 规范；
  3. 345万行 $\times$ 59列宽表挂载；
  4. AST 编译器同义词与注释清洗；
  5. 极速回测仿真与 IS 满贯判定；
  6. CLI 跨目录独立调用。
