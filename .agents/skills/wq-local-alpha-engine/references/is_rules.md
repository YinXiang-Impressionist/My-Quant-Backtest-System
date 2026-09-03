# WorldQuant BRAIN In-Sample (IS) 严格质检与调优字典

WorldQuant BRAIN 平台对任何提交的 Alpha 均执行严格的 In-Sample (样本内) 质检拦截。任何一项未达标，因子均无法上线 (无法获得 `status == ACTIVE`)。

---

## 1. 六大红线指标数学公式与阈值

### ① LOW_SHARPE
- **官方门槛**：$\text{Sharpe} \ge 1.25$
- **计算公式**：
  $$\text{Sharpe} = \frac{\text{Mean}(\text{Daily PnL})}{\text{Std}(\text{Daily PnL})} \times \sqrt{252}$$
- **调优技巧**：
  - 延长滚动排名窗口，例如将 `ts_rank(x, 20)` 提高至 `126` 或 `252`，滤除短期杂波；
  - 引入低相关因子进行线性加权复合（如 `0.5*A + 0.5*B`），分散特质风险。

---

### ② LOW_FITNESS
- **官方门槛**：$\text{Fitness} \ge 1.00$
- **计算公式**：
  $$\text{Fitness} = \text{Sharpe} \times \sqrt{\frac{|\text{Annual Returns}|}{\max(\text{Turnover}, 0.125)}}$$
- **调优技巧**：
  - 换手率惩罚项底线为 $0.125$ (即 12.5%)。若 Turnover 超过 $12.5\%$，换手每翻倍，Fitness 会被平方根压低；
  - 使用加权衰减平滑算子 `ts_decay_linear(x, d)`，可大幅压低换手率并同时保持 Sharpe 稳定。

---

### ③ TURNOVER (换手率区间)
- **官方门槛**：$1.0\% \le \text{Turnover} \le 70.0\%$
- **计算公式**：
  $$\text{Daily Turnover} = \frac{0.5 \sum_i |w_{i,t} - w_{i,t-1}|}{\text{BookSize}}$$
- **调优技巧**：
  - 若换手过高（$>70\%$）：不可直接差分 `ts_delta(x, 1)`，改用 `ts_mean` 或 `ts_decay_linear`；
  - 若换手过低（$<1\%$）：通常是纯基本面财报因子且未结合价量动态调仓，可适当缩短 lookback 或结合月度重平衡。

---

### ④ DRAWDOWN (最大回撤)
- **官方门槛**：$\text{Max Drawdown} < 25.0\%$
- **计算公式**：
  $$\text{Drawdown}_t = \max_{s \le t}(\text{CumPnL}_s) - \text{CumPnL}_t$$
- **调优技巧**：
  - 强制执行行业中性化 `group_neutralize(x, "subindustry")`，避免大盘单边下行或特定行业周期崩塌；
  - 实施 `truncation=0.08`，防止单一重仓股暴雷拖累组合净值。

---

### ⑤ SUB_UNIVERSE_TOP1000 (大市值穿透检验)
- **官方门槛**：$\text{Sub-Universe Sharpe} \ge 1.00$
- **背景与原因**：
  - WorldQuant 官方防范选手构建的 Alpha 仅在小市值股票（流动性差、买不进卖不出）上有效；
  - 引擎在只保留市值排名前 1000 的大票子集中，独立核算 Sharpe。
- **调优技巧**：
  - 在表达式中加入大市值或大成交量加权项：`expr * rank(adv20)` 或 `expr * rank(cap)`；
  - 避免选用微小科目的高偏度比率（小票分母接近 0 产生极端异常大值）。

---

### ⑥ SELF_CORRELATION (自相关熔断拦截)
- **官方红线**：与库内已有因子的日收益相关系数 $< 0.70$（**本地引擎前置严格预警红线为 $< 0.65$**）
- **计算公式**：
  $$\rho = \text{Corr}(\text{PnL}_{\text{new}}, \text{PnL}_{\text{existing}})$$
- **调优技巧**：
  - 严禁对已有因子做微调（如改常数 `126 -> 125`）；
  - 采用跨风格（例如“基本面财务健康”与“价量动量反转”）异构合成，彻底打破同质化。
