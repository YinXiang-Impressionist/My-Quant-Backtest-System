# WorldQuant BRAIN 核心算子数学定义与用法速查手册

本文档收录本地极速量化引擎（`engine/operators.py` 与 `engine/expr_compiler.py`）现已原生支持并向量化加速的全部算子、数学定义、参数要求及量化实战用法。

---

## 1. 截面算子 (Cross-Sectional Operators)

所有截面算子在每日 (`date`) 的全体股票截面上独立执行。

| 算子名称 | 语法与签名 | 数学定义 | 典型用法与说明 |
| :--- | :--- | :--- | :--- |
| `rank` | `rank(x)` | 将 $x$ 转换为百分比排名：<br>$\frac{\text{Rank}(x) - 1}{N - 1} \in [0, 1]$ | 标准化截面信号，消除量纲差异与极端离群值影响。<br>例：`rank(close / ts_delay(close, 20))` |
| `zscore` | `zscore(x)` | $\frac{x - \mu_t}{\sigma_t}$，均值为 0，方差为 1 | 保留相对间距的截面标准化。<br>例：`zscore(sales / assets)` |
| `scale` | `scale(x, target=1.0)` | $\frac{x}{\sum \|x_i\|} \times \text{target}$ | 多空权重绝对值归一化，BookSize 为 target。<br>系统在回测权重计算时会自动调用。 |
| `winsorize` | `winsorize(x, std=4.0)` | 将超过 $\mu \pm \text{std} \times \sigma$ 的极端值截断至边界 | 去极值滤波，防止单个异常财务数据主导组合。 |

---

## 2. 分组算子 (Group-by-Subindustry Operators)

所有分组算子按 `["date", group_col]` 执行组内聚合，默认 `group_col = "subindustry"`（GICS 4 位细分行业分类）。

| 算子名称 | 语法与签名 | 数学定义 | 典型用法与说明 |
| :--- | :--- | :--- | :--- |
| `group_rank` | `group_rank(x, subindustry)` | 细分行业组内的百分比排名 $\in [0, 1]$ | **构建 Alpha 最核心的黄金包装外层**！消除行业固有效应，纯粹挖掘行业内相对强弱。<br>例：`group_rank(operating_income / equity, subindustry)` |
| `group_neutralize` | `group_neutralize(x, subindustry)` | $x - \text{Mean}_{\text{group}}(x)$ | 强制实现组内行业均值中性化，使每行业持仓总多空为 0。<br>例：`group_neutralize(rank(close / open), subindustry)` |
| `group_zscore` | `group_zscore(x, subindustry)` | $\frac{x - \mu_{\text{group}}}{\sigma_{\text{group}}}$ | 行业内的标准化得分。<br>例：`group_zscore(ts_delta(cfo, 63), subindustry)` |

---

## 3. 时序算子 (Time-Series Operators)

所有时序算子自动带 `.over("ticker")`，严格在单个股票内部向前滑动，彻底杜绝跨股票污染与未来函数。

| 算子名称 | 语法与签名 | 数学定义 | 典型用法与说明 |
| :--- | :--- | :--- | :--- |
| `ts_delay` | `ts_delay(x, d)` | $x_{t-d}$（滞后 $d$ 个交易日） | 信号延迟或环比基准。<br>例：`close / ts_delay(close, 5) - 1` |
| `ts_delta` | `ts_delta(x, d)` | $x_t - x_{t-d}$（差分值） | 增量变动或加速度动量。<br>例：`ts_delta(receivable, 63)` |
| `ts_mean` | `ts_mean(x, d)` | $\frac{1}{d} \sum_{i=0}^{d-1} x_{t-i}$（滚动简单移动平均） | 平滑高频噪声。<br>例：`ts_mean(close * volume, 20)` |
| `ts_std_dev`| `ts_std_dev(x, d)` | 过去 $d$ 天的滚动样本标准差 $\sigma_{t,d}$ | 测度价格或基本面指标的离散波动。<br>例：`ts_std_dev(returns, 20)` |
| `ts_rank` | `ts_rank(x, d)` | $x_t$ 在过去 $d$ 天时间序列中的百分比分位数 $\in [0, 1]$ | **时序动量与历史分位数的核心算子**！使指标具备历史纵向可比性。<br>例：`ts_rank(operating_income / equity, 126)` |
| `ts_decay_linear` | `ts_decay_linear(x, d)` | 线性衰减加权均值：<br>$\frac{\sum_{i=1}^d i \cdot x_{t-d+i}}{\sum_{i=1}^d i}$ | **压低换手率 (Turnover) 的终极法宝**！赋予近期更高权重，平滑换手并保持高 Sharpe。<br>例：`ts_decay_linear(returns * adv20, 20)` |
| `ts_corr` | `ts_corr(x, y, d)` | 过去 $d$ 天序列 $x$ 与 $y$ 的 Pearson 滚动相关系数 | 量价背离或基本面与价格协同度。<br>例：`ts_corr(close, volume, 20)` |
| `ts_zscore`| `ts_zscore(x, d)` | $\frac{x_t - \text{ts\_mean}(x, d)}{\text{ts\_std\_dev}(x, d)}$ | 历史自身分位数的偏离度。<br>例：`ts_zscore(fcf / cap, 60)` |
| `ts_max` | `ts_max(x, d)` | $\max(x_{t-d+1}, \dots, x_t)$ | 滚动最高点，突破策略基准。 |
| `ts_min` | `ts_min(x, d)` | $\min(x_{t-d+1}, \dots, x_t)$ | 滚动最低点，支撑或超跌基准。 |
| `ts_sum` | `ts_sum(x, d)` | $\sum_{i=0}^{d-1} x_{t-i}$ | 累计区间总量（如累计分红或成交量）。 |

---

## 4. 数学与逻辑控制函数 (Math & Logic)

| 算子/函数 | 语法与签名 | 行为与说明 |
| :--- | :--- | :--- |
| `if_else` | `if_else(cond, true_val, false_val)` | 向量化条件三元判断：若 `cond` 为真返回 `true_val`，否则返回 `false_val`。<br>例：`if_else(sales > 0, (sales - cogs)/sales, 0.0)` |
| `trade_when`| `trade_when(cond, alpha, -1)` | 条件调仓触发器：仅当 `cond` 成立时更新 `alpha` 仓位，否则保持前日持仓（`-1` 保持前值）。大幅降低换手率。 |
| `signed_power` | `signed_power(x, p)` | $\text{sign}(x) \times \|x\|^p$。保留正负号的幂次变换，常用于缩放非线性敏感度（如 $p=0.5$ 开方压缩极值）。 |
| `abs` | `abs(x)` | 绝对值函数。 |
| `sign` | `sign(x)` | 符号函数：正数返回 $1.0$，负数返回 $-1.0$，零返回 $0.0$。 |
| `log` | `log(x)` | 自然对数变换 $\ln(x)$（负数/零自动置空或保护）。 |

---

## 5. 经典算子复合范式 (Composition Archetypes)

### 范式 1：黄金组内时序分位复合 (The Golden Paradigm)
$$\text{Alpha} = \text{group\_rank}(\text{ts\_rank}(\text{Factor}, d_1), \text{subindustry})$$
- 典型周期：$d_1 \in [63, 126, 252]$（季度、半年度、年度分位数）
- 特点：抗量纲干扰、抗行业系统性冲击、换手率天然适中（10% ~ 20%）。

### 范式 2：双核跨源正交杂交 (Orthogonal Hybridization)
$$\text{Alpha} = w_1 \cdot \text{group\_rank}(\text{Signal}_A, \text{sub}) + w_2 \cdot \text{group\_rank}(\text{Signal}_B, \text{sub})$$
- 经典配比：$0.5 \times \text{ROE} + 0.5 \times \text{CFROA}$，或 $0.6 \times \text{VWAP Reversal} + 0.4 \times \text{Buyback Yield}$。
- 特点：Sharpe 大幅提升至 2.5 ~ 3.5+，最大回撤显著降低。

### 范式 3：高频价量平滑减速降换手 (Turnover Reduction)
$$\text{Alpha} = \text{group\_rank}(\text{ts\_decay\_linear}(\text{Momentum}, 20), \text{subindustry})$$
- 特点：利用线性加权衰减平滑高频信号，换手率直接压减 50% 以上，轻松满足 Fitness $\ge 1.0$。
