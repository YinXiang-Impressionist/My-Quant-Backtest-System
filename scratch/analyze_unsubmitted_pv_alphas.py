"""
从 WorldQuant BRAIN 账号拉取全部未提交 (UNSUBMITTED) 因子，
精准识别出其中的【纯量价 (PV) 因子】，
并在本地 244 万行全量 TOP3000 数据集上运行回测，输出详细对比报告。
"""

import sys
import json
from pathlib import Path
import polars as pl

# 1. 引入 BrainClient
SKILL_DIR = Path(r"C:\Users\xiang\.gemini\config\skills\wq-alpha-research")
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wq_core.brain_api import BrainClient
from engine.simulator import LocalWQSimulator
from data_loader.config import MASTER_PATH

def main():
    print("正在连接 WorldQuant BRAIN 账号并拉取全量 Alpha 列表...")
    client = BrainClient()
    all_alphas = client.get_all_alphas()
    print(f"账户内 Alpha 总数: {len(all_alphas)}")

    # 过滤出所有未提交状态的因子 (非 ACTIVE)
    unsubmitted = [a for a in all_alphas if a.get("status") != "ACTIVE"]
    print(f"未提交 (UNSUBMITTED / REJECTED) 因子数: {len(unsubmitted)}")

    # 纯量价因子过滤规则：排除包含任何财报/基本面/分析师关键词的表达式
    non_pv_tokens = [
        "est_", "eps", "asset", "equity", "income", "sales", "cogs", "receivable",
        "inventory", "cash", "debt", "goodwill", "capex", "fcf", "liabilit",
        "retained", "working_capital", "ebit", "dividend", "tax", "margin",
        "turnover", "pnl", "reacquired", "sharesout", "bookvalue", "enterprise_value"
    ]

    pure_pv_alphas = []
    for a in unsubmitted:
        raw_reg = a.get("regular", "")
        code = raw_reg.get("code", "") if isinstance(raw_reg, dict) else str(raw_reg or "")
        code_clean = code.strip()
        if not code_clean:
            continue
        code_lower = code_clean.lower()
        if not any(token in code_lower for token in non_pv_tokens):
            pure_pv_alphas.append(a)

    print(f"\n成功筛选出 {len(pure_pv_alphas)} 个【纯量价 (PV) 候选因子】！")

    # 加载本地 244 万行全量数据集
    print(f"正在加载本地 244 万行 TOP3000 全量宽表 ({MASTER_PATH})...")
    df = pl.read_parquet(MASTER_PATH)
    sim = LocalWQSimulator(df)

    comparison_records = []

    print("\n" + "="*80)
    print(f"{'Alpha ID':<10} | {'WQ Sharpe':<9} | {'本地 Sharpe':<10} | {'WQ TO(双边)':<11} | {'本地 TO(双边)':<11} | 表达式")
    print("="*80)

    for a in pure_pv_alphas:
        aid = a["id"]
        raw_reg = a.get("regular", "")
        expr = raw_reg.get("code", "") if isinstance(raw_reg, dict) else str(raw_reg or "")
        
        is_metrics = a.get("is", {})
        wq_sharpe = is_metrics.get("sharpe")
        wq_fitness = is_metrics.get("fitness")
        wq_turnover = is_metrics.get("turnover") # WQ 通常是双边
        wq_returns = is_metrics.get("returns")
        wq_drawdown = is_metrics.get("drawdown")

        settings = a.get("settings", {})
        decay = settings.get("decay", 0)
        delay = settings.get("delay", 1)
        neutralization = settings.get("neutralization", "SUBINDUSTRY")

        try:
            m = sim.simulate(
                expression=expr,
                delay=delay,
                decay=decay,
                neutralization=neutralization,
                truncation=0.08,
                alpha_id=aid,
                check_corr=False
            )

            local_sharpe = round(m.sharpe, 3)
            local_fitness = round(m.fitness, 3)
            local_to_twosided = round(m.turnover * 2.0, 3) # 转为双边与 WQ 对标
            local_returns = round(m.returns, 3)
            local_dd = round(m.max_drawdown, 3)

            wq_to_str = f"{wq_turnover*100:.1f}%" if wq_turnover is not None else "N/A"
            loc_to_str = f"{local_to_twosided*100:.1f}%"
            wq_s_str = f"{wq_sharpe:.2f}" if wq_sharpe is not None else "N/A"
            loc_s_str = f"{local_sharpe:.2f}"

            print(f"{aid:<10} | {wq_s_str:<9} | {loc_s_str:<10} | {wq_to_str:<11} | {loc_to_str:<11} | {expr[:40]}...")

            comparison_records.append({
                "id": aid,
                "name": a.get("name", ""),
                "expression": expr,
                "decay": decay,
                "delay": delay,
                "neutralization": neutralization,
                "wq_metrics": {
                    "sharpe": wq_sharpe,
                    "fitness": wq_fitness,
                    "turnover_twosided": wq_turnover,
                    "returns": wq_returns,
                    "drawdown": wq_drawdown,
                },
                "local_metrics": {
                    "sharpe": local_sharpe,
                    "fitness": local_fitness,
                    "turnover_twosided": local_to_twosided,
                    "turnover_onesided": round(m.turnover, 3),
                    "returns": local_returns,
                    "drawdown": local_dd,
                    "runtime_ms": round(m.runtime_ms, 1),
                }
            })
        except Exception as e:
            print(f"{aid:<10} | 模拟执行跳过/失败: {e}")

    out_file = Path("scratch/unsubmitted_pv_comparison.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison_records, f, indent=2, ensure_ascii=False)
    
    print("="*80)
    print(f"全量纯量价因子比对完成，详细 JSON 结果已保存至: {out_file}")

if __name__ == "__main__":
    main()
