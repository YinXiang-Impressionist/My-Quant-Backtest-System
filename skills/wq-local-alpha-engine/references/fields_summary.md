# WorldQuant BRAIN 核心字段与 SEC EDGAR US-GAAP 映射全景速查手册

本文档收录本地极速量化回测引擎 (`master_backtest.parquet`) 现已支持的全部 **59 个核心物理宽表字段**、**自动同义词 Fallback 别名**、**SEC EDGAR XBRL 原始标签映射**及量化常用表达范式。

---

## 快速查询方式 (4 种查询途径)

1. **Web GUI 界面 (推荐)**: 启动 `python gui.py`，点击代码编辑器右上角的 **「📖 字段与算子词典」** 抽屉，即可展开全部分类标签，**鼠标点击任一字段标签将自动插入当前公式光标处**。
2. **CLI 命令行工具**:
   - `python -m cli fields`：全屏打印精美富文本分类表格。
   - `python -m cli fields --search income`：模糊搜索指定关键词（如 `income`, `debt`, `cash`, `eps` 等）。
   - `python -m cli fields --category 资产`：按分类筛选字段。
   - `python -m cli fields --json`：输出标准 JSON 格式供程序化调用。
3. **HTTP REST API**: Web GUI 启动后访问 `GET http://127.0.0.1:8888/api/fields` 获取包含全部列名及同义词映射的 JSON 数据。
4. **底层对齐映射字典**: 查看 `data_loader/wq_sec_field_alignment.json`（收录 1,652 个 WorldQuant 财报特征与 195 个量价特征的计算与来源明细）。

---

## 1. 交易所基础价量字段 (Price-Volume, PV, 共 10 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | 单位/量纲 | 说明与量化常见用法 |
| :--- | :--- | :--- | :--- |
| `close` | - | USD | 当日官方收盘价，基准价格信号 `close / ts_delay(close, 1) - 1` |
| `open` | - | USD | 当日官方开盘价，用于日内跳空与振幅 `(close - open) / open` |
| `high` | - | USD | 当日最高价，日内波动区间 `(high - low) / close` |
| `low` | - | USD | 当日最低价，支撑与反转信号 |
| `volume` | - | 股数 | 当日成交股数，配合价格构建量价背离信号 |
| `vwap` | - | USD | 成交量加权平均价，微观结构价格基准 `(vwap - close) / close` |
| `returns` | - | 无量纲 | 日度收益率 `close / ts_delay(close, 1) - 1` |
| `cap` | - | USD | 当日股票总市值 (Market Cap) |
| `adv20` | - | USD | 过去 20 交易日平均成交金额 `ts_mean(close * volume, 20)`，用于流动性过滤 |
| `shares_outstanding`| `shares`, `sharesout`, `common_shares` | 股数 | 发行在外普通股总数，计算股本扩张与每股指标 |

---

## 2. 资产负债表 - 资产类 (Assets, 共 9 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | SEC XBRL 原始标签 | 经济学含义与量化用途 |
| :--- | :--- | :--- | :--- |
| `assets` | `total_assets` | `Assets` | 企业全部资产总计，ROA 计算的核心分母，规模基准 |
| `assets_curr` | `current_assets` | `AssetsCurrent` | 流动资产合计，短期偿债能力与营运资本计算 |
| `cash` | `cash_and_equivalents` | `CashAndCashEquivalentsAtCarryingValue` | 货币资金与现金等价物，极端市况下的防御安全垫 |
| `cash_st` | `cash_and_short_term_investments` | `CashCashEquivalentsAndShortTermInvestments` | 现金与短期投资总额，高流动性储备 |
| `receivable` | `accounts_receivable` | `AccountsReceivableNetCurrent` | 应收账款净额，衡量回款周期与盈余质量 (Accruals) |
| `inventory` | `inventories` | `InventoryNet` | 存货净额，制造业/消费零售存货周转与积压风险 |
| `ppent` | `property_plant_equipment`, `fixed_assets`, `ppe` | `PropertyPlantAndEquipmentNet` | 固定资产净额 (厂房设备)，重资产扩张度与资产重估 |
| `goodwill` | `total_goodwill` | `Goodwill` | 商誉净额，衡量历史并购溢价与商誉减值雷区 |
| `intangible_assets`| `finite_intangibles` | `IntangibleAssetsNetExcludingGoodwill` | 无形资产净额 (专利/软件/特许权) |

---

## 3. 资产负债表 - 负债与股东权益 (Liabilities & Equity, 共 7 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | SEC XBRL 原始标签 | 经济学含义与量化用途 |
| :--- | :--- | :--- | :--- |
| `liabilities` | `total_liabilities` | `Liabilities` | 总负债，资本结构与财务杠杆率指标 `liabilities / assets` |
| `liabilities_curr`| `current_liabilities` | `LiabilitiesCurrent` | 流动负债合计，衡量短期偿付流动性压力 |
| `total_debt` | `debt` | `LongTermDebtNoncurrent + DebtCurrent` | 有息债务总和，财务杠杆风险与净债务测算 |
| `debt_st` | `short_term_debt`, `debt_current` | `DebtCurrent` | 短期借款与一年内到期的非流动负债 |
| `accounts_payable`| `ap` | `AccountsPayableCurrent` | 应付账款，商业信用与对上下游供应链的议价定价权 |
| `equity` | `stockholders_equity`, `bookvalue` | `StockholdersEquity` | 归属于股东的净资产/股东权益，ROE 计算核心分母 |
| `retained_earnings`| `retained_earnings_accumulated_deficit` | `RetainedEarningsAccumulatedDeficit` | 留存收益，反映公司创办以来的历史未分配利润积累 |

---

## 4. 利润表 (Income Statement, 共 9 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | SEC XBRL 原始标签 | 经济学含义与量化用途 |
| :--- | :--- | :--- | :--- |
| `sales` | `revenues`, `revenue`, `turnover` | `Revenues`, `SalesRevenueNet` | 营业总收入，反映市场份额与成长性扩张速度 |
| `cogs` | `cost_of_goods_sold`, `cost_of_revenue`| `CostOfGoodsAndServicesSold` | 营业成本，直接商品/服务交付成本，毛利计算基础 |
| `gross_profit` | `gp` | `GrossProfit` | 毛利润，衡量产品与商业模式的核心毛利率 `gross_profit / sales` |
| `operating_income`| `ebit`, `op_income` | `OperatingIncomeLoss` | 核心营业利润 (EBIT)，衡量日常主营业务真实造血能力 |
| `net_income` | `income`, `ni`, `net_earnings` | `NetIncomeLoss` | 净利润，底线盈利水平，PE市盈率与净利率分子 |
| `interest_expense`| `interest_and_debt_expense` | `InterestAndDebtExpense` | 利息费用，债务利息负担与利息保障倍数计算 |
| `rd_expense` | `rnd_expense`, `research_and_development` | `ResearchAndDevelopmentExpense` | 研发投入费用，科技创新驱动力与隐形资本积累 |
| `sga_expense` | `selling_general_administrative` | `SellingGeneralAndAdministrativeExpense` | 销售、一般与行政费用，管理费用控制效率 |
| `income_tax` | `income_tax_expense`, `tax_expense` | `IncomeTaxExpenseBenefit` | 所得税费用，实际有效税率分析 |

---

## 5. 现金流量表 (Cash Flow, 共 8 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | SEC XBRL 原始标签 | 经济学含义与量化用途 |
| :--- | :--- | :--- | :--- |
| `cashflow_op` | `cfo`, `operating_cashflow` | `NetCashProvidedByUsedInOperatingActivities` | 经营活动净现金流，验证利润真实性的黄金锚点 |
| `capex` | `capital_expenditure` | `PaymentsToAcquirePropertyPlantAndEquipment` | 资本性开支，购建固定资产投资支出 |
| `fcf` | `free_cash_flow` | `cashflow_op - capex` | 自由现金流 (Free Cash Flow)，股东真实自由回报 |
| `cashflow_invst` | `investing_cashflow` | `NetCashProvidedByUsedInInvestingActivities` | 投资活动净现金流，外延并购与资产扩张信号 |
| `cashflow_fin` | `financing_cashflow` | `NetCashProvidedByUsedInFinancingActivities` | 筹资活动净现金流，股债融资与分红回购还债 |
| `cashflow_dividends`| `dividends`, `dividends_paid` | `PaymentsOfDividends` | 派发现金股利分红，红利收益率与股东回报信号 |
| `depreciation` | `depr`, `depreciation_and_amortization` | `DepreciationDepletionAndAmortization` | 折旧与摊销，非现金支出会计调整 |
| `value_of_shares_reacquired_during_period` | - | `PaymentsForRepurchaseOfCommonStock` | 股票回购金额，美股注销式回购牛市引擎 |

---

## 6. 财务比率与估值衍生 (Ratios & Valuation, 共 8 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | 计算公式 / 来源 | 经济学含义与量化用途 |
| :--- | :--- | :--- | :--- |
| `working_capital` | `nwc` | `assets_curr - liabilities_curr` | 净营运资本，短期流动性安全厚度 |
| `current_ratio` | `cr` | `assets_curr / liabilities_curr` | 流动比率，短期偿债保障倍数 |
| `inventory_turnover`| `inv_turnover` | `cogs / inventory` | 存货周转率，运营周转效率 |
| `ebitda` | `operating_income_plus_depr` | `operating_income + depreciation` | 息税折旧摊销前利润，跨资本结构估值指标 |
| `roic` | `return_on_invested_capital` | `operating_income / (equity + total_debt)` | 投资资本回报率，巴菲特护城河核心量化指标 |
| `asset_turnover` | `total_asset_turnover` | `sales / assets` | 总资产周转率，杜邦分析核心周转支柱 |
| `ev` | `enterprise_value` | `cap + total_debt - cash` | 企业价值 (Enterprise Value)，收购/并购整体估值 |
| `est_eps` | - | 分析师一致预期 EPS 衍生 | 分析师盈利预测修正与预期差因子 |

---

## 7. 风险模型与波动率指标 (Risk & Volatility, 共 3 列)

| 字段名称 (Column) | 常用别名 (Synonyms) | 说明与量化用途 |
| :--- | :--- | :--- |
| `beta_last_30_days_spy` | `beta`, `beta_30`, `market_beta` | 过去 30 个交易日个股相对标普500大盘指数的滚动Beta系数，市场系统性敏感度 |
| `volatility_20` | `vol_20` | 过去 20 个交易日年化已实现波动率，短周期波动率反转/规避 |
| `volatility_60` | `vol_60` | 过去 60 个交易日年化已实现波动率，中周期风险基准 |

---

## 8. 截面与分组标识 (Metadata & Grouping, 共 5 列)

| 字段名称 (Column) | 类型 | 说明与量化用法 |
| :--- | :--- | :--- |
| `ticker` | 字符串 (String) | 股票代码 (如 `AAPL`, `MSFT`, `NVDA`, `AMZN`) |
| `date` | 日期 (Date) | 交易日时间序列主键 (格式 `YYYY-MM-DD`) |
| `filed_date` | 日期 (Date) | SEC 官方财报披露日（严格采用点对点 Point-in-Time 机制，杜绝未来函数） |
| `subindustry` | 字符串 (String) | GICS 4 位细分行业分类名称，**组内中性化与分组排序的强制基准分组列** |
| `is_top1000` | 布尔值 (Boolean) | 当日市值排名前 1000 大股票标记，用于 Universe 稳健性检验 |

---

## 经典因子表达式范例

1. **巴菲特护城河资本回报率 (ROIC Momentum)**:
   `group_rank(ts_rank(roic, 126), subindustry)`
2. **净资产收益率质量杜邦模型 (DuPont ROE)**:
   `group_rank(ts_zscore((sales / assets) * (operating_income / sales) * (assets / equity), 60), subindustry)`
3. **真实自由现金流收益率 (FCF Yield)**:
   `group_rank((cashflow_op - capex) / cap, subindustry)`
4. **低杠杆高毛利质量防守 (Quality Defensiveness)**:
   `group_rank(gross_profit / sales, subindustry) - group_rank(total_debt / assets, subindustry)`
5. **应收账款异动率 (Accrual Anomaly)**:
   `-group_rank(ts_delta(receivable, 63) / assets, subindustry)`
6. **低波动率异象 (Low Volatility Anomaly)**:
   `-group_rank(volatility_60, subindustry)`
