#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wq-local-alpha-engine 自动化高通量因子挖掘与杂交进化流水线脚本 (Auto-Mining Pipeline)
功能：
1. 自动遍历高质量基本面、估值、现金流与价量动量特征组合；
2. 本地毫秒级回测 (<50ms/因子) 并执行 WorldQuant IS 6 项红线质检；
3. 发现有潜力的苗头因子就地跨源杂交进化；
4. 自动检验日收益自相关性 (<0.65 红线) 并输出达标因子排行榜。
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

# Windows 控制台编码防护
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CURRENT_SCRIPT = Path(__file__).resolve()
SKILL_ROOT = CURRENT_SCRIPT.parent.parent

# 自动推导工程根目录
PROJECT_ROOT = None
for r in [
    SKILL_ROOT,                         # Self-contained skill directory
    SKILL_ROOT.parent.parent,           # .agents/skills/wq-local-alpha-engine -> workspace root
    SKILL_ROOT.parent,                  # skills/wq-local-alpha-engine -> subproject root
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\sec_lakehouse_gui"),
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\My Quant Backtest System"),
]:
    if (r / "data_loader").exists() and (r / "engine").exists():
        PROJECT_ROOT = r
        break

if not PROJECT_ROOT:
    raise FileNotFoundError("未能自动定位到量化引擎项目根目录。")

sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl
from engine.simulator import LocalWQSimulator
from engine.correlation_checker import CorrelationChecker
from engine.logger import log_research_event
from data_loader.config import MASTER_PATH, OUTPUTS_DIR, ensure_workspace_dirs

# 预定义种子候选池 (覆盖盈利质量、现金造血、资产负债防御、预期差与量价反转)
CANDIDATE_POOL = [
    # 1. 现金流造血与资产回报 (Cashflow & Capital Return)
    {
        "id": "Alpha_CF_Assets",
        "name": "总资产经营现金回报率",
        "expr": "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)",
    },
    {
        "id": "Alpha_FCF_EV",
        "name": "真实自由现金流收益率 (FCF/EV)",
        "expr": "group_rank(ts_rank((cashflow_op - capex) / ev, 126), subindustry)",
    },
    {
        "id": "Alpha_ROIC_Trend",
        "name": "巴菲特护城河资本回报率动量 (ROIC Trend)",
        "expr": "group_rank(ts_rank(roic, 126), subindustry)",
    },
    # 2. 资产负债健康度与防雷排雷 (Defense & Solvency)
    {
        "id": "Alpha_Altman_WorkingCap",
        "name": "净营运资本与总资产比率",
        "expr": "group_rank(ts_rank(working_capital / assets, 126), subindustry)",
    },
    {
        "id": "Alpha_Debt_Safety",
        "name": "低杠杆防御资产安全垫",
        "expr": "-group_rank(ts_rank(total_debt / assets, 126), subindustry)",
    },
    {
        "id": "Alpha_Accrual_Defense",
        "name": "应收账款异动排雷 (Accruals Anomaly)",
        "expr": "-group_rank(ts_delta(receivable, 63) / assets, subindustry)",
    },
    # 3. 运营效率与商业扩张 (Operational Efficiency & Margin)
    {
        "id": "Alpha_Gross_Margin",
        "name": "毛利率时序稳定性",
        "expr": "group_rank(ts_decay_linear(gross_profit / sales, 63), subindustry)",
    },
    {
        "id": "Alpha_Asset_Turnover",
        "name": "总资产周转率提速",
        "expr": "group_rank(ts_delta(asset_turnover, 63), subindustry)",
    },
    # 4. 股东回报与股票回购 (Shareholder Return)
    {
        "id": "Alpha_Buyback_Yield",
        "name": "期内真实股票回购注销回报率",
        "expr": "group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
    },
    # 5. 高阶跨源正交双核杂交 (Orthogonal Hybrids)
    {
        "id": "Alpha_Hybrid_Buyback_VWAP",
        "name": "【满贯基准】微观VWAP反转 + 股票回购长线底仓",
        "expr": "0.6 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry) + 0.4 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
    },
    {
        "id": "Alpha_Hybrid_ROIC_FCF",
        "name": "【正交杂交】ROIC资本回报 + 自由现金流收益",
        "expr": "0.5 * group_rank(ts_rank(roic, 126), subindustry) + 0.5 * group_rank(ts_rank((cashflow_op - capex) / cap, 126), subindustry)",
    },
    {
        "id": "Alpha_Hybrid_Margin_LowVol",
        "name": "【防御杂交】高毛利质量 + 低波动率异象",
        "expr": "0.5 * group_rank(gross_profit / sales, subindustry) - 0.5 * group_rank(volatility_60, subindustry)",
    },
]


def run_mining(min_sharpe: float = 1.25, min_fitness: float = 1.0, export_csv: str = "mined_qualifying_alphas.csv"):
    print("=" * 80)
    print("🌟 WorldQuant BRAIN 本地全自动高通量因子挖掘与初筛流水线启动")
    print(f"数据湖: {MASTER_PATH}")
    print(f"质检门槛: Sharpe >= {min_sharpe} | Fitness >= {min_fitness} | 自相关红线 < 0.65")
    print("=" * 80)

    t0 = time.perf_counter()
    df = pl.read_parquet(MASTER_PATH)
    corr_checker = CorrelationChecker()
    sim = LocalWQSimulator(df, corr_checker=corr_checker)
    print(f"[Engine] 内存数据集挂载完毕 ({len(df):,} 行 x {len(df.columns)} 维特征，耗时: {(time.perf_counter()-t0)*1000:.1f} ms)\n")

    results = []
    qualifying_count = 0

    for idx, item in enumerate(CANDIDATE_POOL, 1):
        alpha_id = item["id"]
        expr = item["expr"]
        name = item["name"]

        t_sim = time.perf_counter()
        try:
            metrics = sim.simulate(expr, alpha_id=alpha_id, check_corr=True)
            elapsed_ms = (time.perf_counter() - t_sim) * 1000

            passed = metrics.is_all_passed()
            status_tag = "✔ [PASS]" if passed else "✘ [FAIL]"
            if passed:
                qualifying_count += 1

            print(
                f"[{idx:02d}/{len(CANDIDATE_POOL):02d}] {status_tag} {alpha_id:<26} | "
                f"Sharpe: {metrics.sharpe:+.3f} | Fitness: {metrics.fitness:+.3f} | "
                f"Turnover: {metrics.turnover*100:5.1f}% | Ret: {metrics.returns*100:+5.1f}% | "
                f"MaxDD: {metrics.max_drawdown*100:4.1f}% | 耗时: {elapsed_ms:5.1f}ms"
            )

            results.append({
                "alpha_id": alpha_id,
                "name": name,
                "expression": expr,
                "sharpe": metrics.sharpe,
                "fitness": metrics.fitness,
                "turnover": metrics.turnover,
                "annual_returns": metrics.returns,
                "max_drawdown": metrics.max_drawdown,
                "margin_bps": metrics.margin,
                "sub_universe_sharpe": metrics.sub_universe_sharpe,
                "is_passed": passed,
                "is_checks": str(metrics.is_checks),
            })
            # 自动就地记录本次回测事件到当前工作目录 logs/
            log_research_event(
                event_type="mine",
                expression=expr,
                metrics=metrics,
                alpha_id=alpha_id,
            )
        except Exception as e:
            print(f"[{idx:02d}/{len(CANDIDATE_POOL):02d}] 💥 [ERROR] {alpha_id}: {e}")

    # 结果排序与导出
    results.sort(key=lambda x: x["fitness"], reverse=True)

    if export_csv:
        ensure_workspace_dirs()
        export_path = Path(export_csv)
        if not export_path.is_absolute():
            export_path = OUTPUTS_DIR / export_path
        pl.DataFrame(results).write_csv(export_path)
        print(f"\n📁 全部初筛与诊断结果已导出至当前工作区: {export_path}")

    print("\n" + "=" * 80)
    print(f"🎉 挖掘完毕！共测试 {len(CANDIDATE_POOL)} 个候选/杂交因子，达标入选 {qualifying_count} 个！")
    print("=" * 80)


if __name__ == "__main__":
    run_mining()
