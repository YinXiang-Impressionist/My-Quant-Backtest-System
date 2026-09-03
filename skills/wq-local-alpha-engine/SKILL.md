---
name: wq-local-alpha-engine
description: "WorldQuant BRAIN 本地超快速 (<20ms) 离线量化回测与因子初筛引擎研发指南。用于：基于本地 Polars 向量化引擎与 SEC EDGAR 真实无未来数据极速挖掘 Alpha、运行毫秒级回测、诊断 IS 6 项红线质检（Sharpe/Fitness/Turnover/Drawdown/Sub-Universe TOP1000）、前置拦截日收益自相关（< 0.65）、杂交进化高分因子以及自动化线上提交。触发词包含：'本地极速挖因子'、'本地引擎挖因子'、'开始本地挖掘'、'用本地引擎测试因子'、'基于本地回测挖新因子'、'全自动本地挖掘流水线'、'/wq-local-alpha-engine'。"
---

# WorldQuant BRAIN 本地极速量化研发与自进化引擎 Skill

> **一句话开箱即用**：
> 在任意会话中，只需对助手说：**“开始本地极速挖因子”** 或 **“用本地引擎测试因子”**，助手便会自动挂载本项目本地离线高保真数据集（40,200+ 行无前视偏差价量与 SEC EDGAR 财报宽表），在 **15ms ~ 25ms** 内完成单次回测、执行 IS 六项质检与自相关拦截，并在发现高分苗头时就地多轮杂交进化！

---

## 1. 核心架构与本地先行流水线 (Local-First Hybrid Pipeline)

```
用户指令 (“开始本地极速挖因子”)
  ├── 1. 挂载本地离线客观数据库 (Point-in-Time, 100% 零未来函数)
  │    └── data/master_backtest.parquet (date >= filed_date, delay=1, TOP3000池)
  ├── 2. 候选特征生成与 AST 分层编译
  │    └── 利用 TSExtractor 将时序算子 (.over("ticker")) 与截面算子分层解耦
  ├── 3. 本地毫秒级回测仿真 (<20ms / 因子)
  │    ├── SUBINDUSTRY 行业截面中性化 + 0.08 极值截断 + scale(1.0)
  │    ├── 精确计算单边换手率: 0.5 * sum(|pos_t - pos_{t-1}|)
  │    └── 评估 Sharpe, Fitness, Turnover, Drawdown, Margin
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

工程根目录内置统一的高性能命令行工具 `cli.py`：

### 2.1 单因子即时诊断与回测
```powershell
python -m cli run --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)" --id "Alpha_ROE_Trend"
```
- **参数说明**：
  - `--commit`：回测通过后自动将该因子的日收益 PnL 序列写入 `data/committed_alphas_pnl.parquet`，供后续自相关性拦截比对。
  - `--submit`：自动在 `data/submissions/` 生成标准 JSON 提交包并可直接调用线上 API。
  - `--no-corr`：跳过自相关性检测（快速测试时可用）。

### 2.2 批量因子高通量初筛与排行榜
```powershell
python -m cli batch --file alphas_sample.txt --export qualifying_alphas.csv
```
- 读取因子清单文件，以每秒 50+ 个因子的吞吐量快速完成并发回测；
- 按照 **Fitness** 降序渲染美观的富文本终端排行榜；
- 自动将符合 Sharpe $\ge 1.25$ 与 Fitness $\ge 1.0$ 的优质因子导出为 CSV。

### 2.3 因子库自相关性深度扫描与拦截
```powershell
python -m cli check-corr --expr "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)"
```
- 输出待测因子与本地已提交因子库中所有历史因子的详细 Pearson 相关系数表；
- 超过 0.65 红线自动高亮标红并告警。

### 2.4 数据集状态概览
```powershell
python -m cli dataset --info
```

---

## 3. WorldQuant IS 六项严格质检红线与调优手册

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
4. **线性加权衰减平滑动量 (Decay-Linear Momentum)**：
   ```python
   group_rank(ts_decay_linear(returns * adv20, 20), subindustry)
   ```

### 4.2 算子兼容速查表
- **截面类**：`rank(x)`, `zscore(x)`, `scale(x, 1.0)`, `winsorize(x, std=4.0)`
- **分组类**：`group_rank(x, subindustry)`, `group_zscore(x, subindustry)`, `group_neutralize(x, subindustry)`
- **时序类**：`ts_rank(x, d)`, `ts_decay_linear(x, d)`, `ts_std_dev(x, d)`, `ts_corr(x, y, d)`, `ts_zscore(x, d)`, `ts_delay(x, d)`, `ts_delta(x, d)`, `ts_mean(x, d)`
- **数学与逻辑**：`if_else(cond, true_val, false_val)`, `trade_when(cond, alpha, -1)`, `signed_power(x, p)`, `log(x)`, `abs(x)`, `sign(x)`

---

## 5. 核心字段与 SEC EDGAR 映射字典

在本地宽表 `master_backtest.parquet` 中已预对齐好无前视偏差的核心字段：

| 本地字段名 | WQ 对应字段名 | SEC EDGAR 原版 XBRL Tag | 财务报表属性 | 适用风格 |
| :--- | :--- | :--- | :--- | :--- |
| `operating_income` | `operating_income` / `ebit` | `OperatingIncomeLoss` | 利润表核心营业利润 | Quality, Value |
| `sales` | `sales` / `revenues` | `Revenues` / `SalesRevenueNet` | 利润表营业总收入 | Growth, Size |
| `net_income` | `net_income` | `NetIncomeLoss` | 利润表净利润 | Earnings Quality |
| `cogs` | `cogs` | `CostOfGoodsAndServicesSold` | 营业成本 | Margin, Efficiency |
| `equity` | `equity` / `stockholders_equity` | `StockholdersEquity` | 资产负债表股东权益 | ROE, Value |
| `assets` | `assets` / `total_assets` | `Assets` | 资产负债表总资产 | ROA, Capital Structure |
| `cash` | `cash` | `CashAndCashEquivalentsAtCarryingValue` | 资产负债表现金及等价物 | Solvency, Defense |
| `receivable` | `receivable` | `AccountsReceivableNetCurrent` | 应收账款 | Accrual, Quality |
| `inventory` | `inventory` | `InventoryNet` | 存货 | Supply Chain, Turnover |
| `cashflow_op` | `cashflow_op` / `cfo` | `NetCashProvidedByUsedInOperatingActivities` | 现金流量表经营现金流 | Quality, Cash Flow |
| `capex` | `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` | 资本支出 | FCF, Reinvestment |
| `close`, `open`, `high`, `low`, `volume` | 交易所价量 | 官方交易所复权价量 | PV 基础价量 | Momentum, Reversal, Volatility |
| `adv20` | `adv20` | `ts_mean(close * volume, 20)` | 20日成交均额 | Liquidity, Size weighting |
| `subindustry` | `subindustry` | GICS 行业聚类分类 | 分组与中性化基准 | Neutralization |
| `is_top1000` | Sub-Universe | 市值前1000标尺 | 穿透检验基准 | IS Sub-Universe check |

---

## 6. 自主进化研发实战模板 (Prompt Execution SOP)

当用户说 **“开始本地极速挖因子”** 时，Agent 应当执行以下闭环：

1. **第 1 步：生成候选种子**：选取 3~5 个具有清晰经济学逻辑的候选表达式（涵盖 ROE 趋势、资产周转率、真实现金流回报、杠杆变化）；
2. **第 2 步：毫秒级初筛**：直接调用 `LocalWQSimulator` 或 `python -m cli batch` 对候选种子进行回测；
3. **第 3 步：见苗头即进化 (Evolve)**：
   - 若发现某因子 Sharpe $\ge 1.0$ 但其他指标未满贯，**禁止直接丢弃**，立即将其与正交的低相关特征（如现金流、动量或资产周转）进行双核加权杂交（如 `0.5*A + 0.5*B`）；
4. **第 4 步：自相关拦截检验**：调用 `CorrelationChecker` 扫描日收益序列，验证与库内所有因子的最大相关系数 $< 0.65$；
5. **第 5 步：入库并提交**：将满贯因子执行 `--commit` 写入本地已提交因子库，并生成 WorldQuant 官方 JSON 提交单！

---

## 7. 线上正式提交与元数据规范 (Submission & Metadata Standards)

⚠️ **强制军规**：**严禁提交任何未命名、无分类标签的“裸 Alpha”！**
提交一个因子不仅仅是调用 `/submit`，**必须在提交前或提交后立即调用官方 API (`PATCH /alphas/{id}`) 补充完整的专业元数据**，确保账户内策略可读、可溯源且符合 WorldQuant 顶级量化标准。

### 7.1 因子命名规范 (Naming Conventions)
命名统一遵循：`[大类前缀]_[核心经济逻辑]_[子策略]_[周期参数]`

| 风格大类 | 前缀代号 | 示例名称 | 适用策略与逻辑说明 |
| :--- | :--- | :--- | :--- |
| **基本面质量** | `QAL_` | `QAL_ROA_RecSalesScissors_126` | 营业利润总资产回报、应收营收剪刀差排雷 |
| **现金流与收益** | `FCF_` | `FCF_YLD_ReceivableTurnover_126` | 自由现金流收益率 (FCF/EV)、应收账款周转提速 |
| **营运与股东回报** | `OPS_` | `OPS_Shareholder_BuybackYield_252` | 真实股票回购注销回报率、总资产周转率 |
| **分析师预期** | `ANL_` | `ANL_MOM_Beneish_Manip_Rev126` | 分析师超预期盈利上修、Beneish M-Score 操纵防御 |
| **跨界双核杂交** | `HYB_` | `HYB_VWAP_BuybackYield_126_252` | VWAP 反转动量 + 真实股票回购长线底仓杂交 |
| **纯量价动量** | `MOM_` | `MOM_VWAP_Reversal_Decay10` | 典型微观价量、均值回归、波动率动量 |

### 7.2 官方元数据枚举约束与色标方案 (Category & Color Scheme)
- **`category` (官方严格枚举)**：
  - `FUNDAMENTAL`：财务报表质量、现金流、股东回报类策略；
  - `PRICE_VOLUME`：纯交易所量价反转、动量、波动率、流动性冲击；
  - `ANALYST`：卖方分析师预测、盈利调整动量。
  *(注：官方禁止传入非枚举字符串，杂交策略根据主驱动选择 `PRICE_VOLUME` 或 `FUNDAMENTAL`)*
- **`color` (标准色标)**：
  - `GREEN`：现金流收益率、股东回购与资产负债表防御；
  - `BLUE`：盈利能力、ROE/ROA 资产营运质量；
  - `PURPLE`：正交双核杂交策略、分析师超预期修正；
  - `ORANGE` / `YELLOW`：纯量价动量与反转策略。
- **`tags` (3~5 个英文下划线标签)**：
  例如：`['VWAP_Reversal', 'Mean_Reversion', 'Share_Repurchase', 'Buyback_Yield', 'Orthogonal_Hybrid']`
- **`regular.description` (专业英文经济学论述)**：
  用 1~2 句严谨的英文清晰阐述策略的理论基础与加权配比。

### 7.3 自动化提交与元数据封装 SOP (Python 模板)
```python
def submit_and_enrich_alpha(client, alpha_id: str, metadata: dict):
    # 1. 立即补全元数据
    patch_payload = {
        "name": metadata["name"],
        "category": metadata["category"],
        "color": metadata.get("color", "PURPLE"),
        "tags": metadata.get("tags", []),
        "regular": {
            "description": metadata.get("description", "")
        }
    }
    client.session.patch(f"https://api.worldquantbrain.com/alphas/{alpha_id}", json=patch_payload)
    
    # 2. 调用正式提交
    sub_res = client.session.post(f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit")
    assert sub_res.status_code in (200, 201), f"提交失败: {sub_res.text}"
```

