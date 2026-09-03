# WorldQuant BRAIN 核心字段与 SEC EDGAR US-GAAP 映射速查手册

本文档为 Agent 在构思 Alpha 表达式时提供可直接在本地离线宽表 (`master_backtest.parquet`) 中参与回测的高质量特征字段。

---

## 1. 核心三张表基本面字段 (Fundamentals - SEC EDGAR XBRL)

| 字段名称 (WQ Field) | 同义词自动 Fallback | SEC XBRL 原始标签 | 所属报表 | 经济学含义与常见用途 |
| :--- | :--- | :--- | :--- | :--- |
| `operating_income` | `ebit`, `op_income` | `OperatingIncomeLoss` | 利润表 | 核心主营业务营业利润，衡量企业日常经营造血能力 (EBIT) |
| `sales` | `revenues`, `revenue` | `Revenues`, `SalesRevenueNet` | 利润表 | 营业总收入，反映企业商业扩张速度与市场份额规模 |
| `net_income` | `ni`, `net_earnings` | `NetIncomeLoss` | 利润表 | 净利润，底线盈利水平，用于计算市盈率与净利率 |
| `cogs` | `cost_of_revenue` | `CostOfGoodsAndServicesSold` | 利润表 | 营业成本，与 `sales` 结合计算毛利率 (`(sales - cogs)/sales`) |
| `equity` | `stockholders_equity` | `StockholdersEquity` | 资产负债表 | 归属于股东的净资产/股东权益，ROE 计算的核心分母 |
| `assets` | `total_assets` | `Assets` | 资产负债表 | 企业全部资产总和，ROA 计算核心分母，资产利用率基准 |
| `cash` | `cash_and_equivalents` | `CashAndCashEquivalentsAtCarryingValue` | 资产负债表 | 账面现金与高流动性等价物，衡量极端市场环境下的安全边际 |
| `receivable` | `accounts_receivable` | `AccountsReceivableNetCurrent` | 资产负债表 | 应收账款，衡量应收回款周期与应计收益质量 (Accruals) |
| `inventory` | `inventories` | `InventoryNet` | 资产负债表 | 存货净额，制造业与零售业周转速度指标 |
| `cashflow_op` | `cfo`, `operating_cashflow` | `NetCashProvidedByUsedInOperatingActivities` | 现金流量表 | 经营活动产生的真实净现金流量，验证利润真实性的黄金锚点 |
| `capex` | `capital_expenditure` | `PaymentsToAcquirePropertyPlantAndEquipment` | 现金流量表 | 资本开支，用于计算企业自由现金流 FCF (`cashflow_op - capex`) |
| `shares_outstanding`| `shares` | `CommonStockSharesOutstanding` | 股本总数 | 发行在外普通股股数，用于计算市值与每股指标 |

---

## 2. 交易所基础价量字段 (Price-Volume, PV)

| 字段名称 | 单位/量纲 | 说明与量化用法 |
| :--- | :--- | :--- |
| `close` | USD | 当日官方收盘价 (复权/不复权)，基准价格信号 |
| `open` | USD | 当日官方开盘价，可用于日内价差 `(close - open) / open` |
| `high` | USD | 当日最高价，波动区间构建 `(high - low) / close` |
| `low` | USD | 当日最低价，振幅与反转计算 |
| `volume` | 股数 | 当日成交量，配合价格构建量价背离信号 |
| `returns` | 无量纲 | 日度收益率 `close / shift(close, 1) - 1` |
| `adv20` | USD | 过去 20 交易日平均成交金额 `ts_mean(close * volume, 20)`，用于流动性过滤与成交量加权 |
| `cap` | USD | 总市值 (Market Capitalization) |
| `subindustry` | 字符串 | GICS 4 位细分行业分类名称，截面中性化的强制基准分组列 |
| `is_top1000` | 布尔值 (Boolean) | 当前交易日总市值排名前 1000 大股票标记，用于 Sub-Universe 检验 |

---

## 3. 常用派生组合与经典因子范式

1. **总资产现金回报率 (Cash Flow Return on Assets, CFROA)**:
   `cashflow_op / assets`
2. **净资产收益率 (ROE)**:
   `operating_income / equity`
3. **真实自由现金流收益率 (FCF Yield)**:
   `(cashflow_op - capex) / cap`
4. **应收账款异动率 (Accrual Anomaly)**:
   `ts_delta(receivable, 63) / assets`
5. **毛利率稳定性 (Gross Margin Trend)**:
   `ts_decay_linear((sales - cogs) / sales, 63)`
