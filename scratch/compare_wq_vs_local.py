import sys
import json
import polars as pl
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.simulator import LocalWQSimulator
from engine.correlation_checker import CorrelationChecker
from data_loader.config import MASTER_PATH

# 1. 加载数据集
df = pl.read_parquet(MASTER_PATH)
sim = LocalWQSimulator(df, corr_checker=CorrelationChecker())

# 2. 定义测试因子清单与 WorldQuant 线上实测基准
factors = [
    {
        "id": "LL9AnWMa",
        "name": "商誉悬顶排雷 (252d 稀释)",
        "expr": "0.35 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.65 * group_rank(ts_rank(-goodwill / equity, 252), subindustry)",
        "wq_sharpe": 1.64,
        "wq_fitness": 1.14,
        "wq_turnover": 0.121,
        "wq_corr": 0.644,
        "wq_status": "🟢 达标（全绿，备选上线）",
    },
    {
        "id": "wpYMJE0p",
        "name": "存货激增排雷 (252d 稀释)",
        "expr": "0.35 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.65 * group_rank(ts_rank(-ts_delta(inventory, 252) / (cogs + 0.01 * assets), 252), subindustry)",
        "wq_sharpe": 2.41,
        "wq_fitness": 1.99,
        "wq_turnover": 0.129,
        "wq_corr": 0.717,
        "wq_status": "🟡 收益极高，临界线微调中",
    },
    {
        "id": "QP3L2ZE5",
        "name": "应收周转变现 (252d 稀释)",
        "expr": "0.35 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.65 * group_rank(ts_rank(sales / (receivable + 0.01 * assets), 252), subindustry)",
        "wq_sharpe": 1.96,
        "wq_fitness": 1.31,
        "wq_turnover": 0.125,
        "wq_corr": 0.727,
        "wq_status": "🟡 待解耦",
    },
    {
        "id": "gJQER8Kl",
        "name": "DSRI应收激增 (252d 稀释)",
        "expr": "0.35 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.65 * group_rank(ts_rank(-ts_delta(receivable, 252) / assets, 252), subindustry)",
        "wq_sharpe": 2.06,
        "wq_fitness": 1.56,
        "wq_turnover": 0.131,
        "wq_corr": 0.854,
        "wq_status": "⚠️ 与线上 GrdP5555 同源共振",
    },
    {
        "id": "JjxZgaVl",
        "name": "主营利润×DSRI (252d 稀释)",
        "expr": "0.35 * group_rank(ts_rank(operating_income / equity, 252), subindustry) + 0.65 * group_rank(ts_rank(-ts_delta(receivable, 252) / assets, 252), subindustry)",
        "wq_sharpe": 1.86,
        "wq_fitness": 1.29,
        "wq_turnover": 0.074,
        "wq_corr": 0.766,
        "wq_status": "⚠️ 与线上 GrdP5555 排雷项同源",
    },
    {
        "id": "RRVnrlNg",
        "name": "Ⅳ. 真实股票回购注销回报率",
        "expr": "group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
        "wq_sharpe": 1.50,
        "wq_fitness": 1.22,
        "wq_turnover": 0.121,
        "wq_corr": 0.572,
        "wq_status": "🎉 正式上线 (status == ACTIVE)",
    },
    {
        "id": "78ZEdNEQ",
        "name": "Ⅱ. 收盘价对VWAP偏离反转 (高频)",
        "expr": "group_rank(ts_rank(-(close / vwap - 1), 60), subindustry)",
        "wq_sharpe": 2.15,
        "wq_fitness": 0.56,
        "wq_turnover": 1.303,
        "wq_corr": 0.072,
        "wq_status": "🟡 极致正交，换手偏高",
    },
    {
        "id": "KPOjLovj",
        "name": "Ⅷ. 分析师 35% × 回购 65%",
        "expr": "0.35 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.65 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
        "wq_sharpe": 1.96,
        "wq_fitness": 1.58,
        "wq_turnover": 0.174,
        "wq_corr": 0.718,
        "wq_status": "🟡 收益强悍，分析师触发自相关",
    },
    {
        "id": "Amihud_20d",
        "name": "Ⅱ. Amihud 20d非流动性冲击",
        "expr": "group_rank(ts_rank(ts_mean(abs(returns) / (volume * close + 10000), 20), 252), subindustry)",
        "wq_sharpe": None,
        "wq_fitness": None,
        "wq_turnover": None,
        "wq_corr": None,
        "wq_status": "❌ 线上嵌套层级深运算超时熔断",
    },
    {
        "id": "O0rEGQrb",
        "name": "Ⅷ. 20% 分析师 × 80% 股东回购",
        "expr": "0.20 * group_rank(ts_rank(est_eps / close, 252), subindustry) + 0.80 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
        "wq_sharpe": 1.75,
        "wq_fitness": 1.43,
        "wq_turnover": 0.150,
        "wq_corr": 0.653,
        "wq_status": "🟢 完美达标！全绿！备选上线",
    },
    {
        "id": "A10MGqLR",
        "name": "Ⅷ. 35% FCF × 65% 股东回购",
        "expr": "0.35 * group_rank(ts_rank(fcf / ev, 252), subindustry) + 0.65 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
        "wq_sharpe": 1.75,
        "wq_fitness": 1.35,
        "wq_turnover": 0.161,
        "wq_corr": 0.714,
        "wq_status": "🟡 指标全绿，与 GrdP5555 轻度同源",
    },
    {
        "id": "xAY0dKEJ",
        "name": "Ⅱ. VWAP 偏离反转 + ts_decay 控换手",
        "expr": "group_rank(ts_decay_linear(ts_rank(-(close / vwap - 1), 126), 15), subindustry)",
        "wq_sharpe": 1.75,
        "wq_fitness": 0.80,
        "wq_turnover": 0.467,
        "wq_corr": 0.156,
        "wq_status": "🟡 换手砍至 46%，超低相关",
    }
]

comparison_results = []

for item in factors:
    print(f"正在本地回测: {item['id']} - {item['name']}...")
    try:
        m = sim.simulate(
            expression=item["expr"],
            delay=1,
            neutralization="SUBINDUSTRY",
            truncation=0.08,
            alpha_id=item["id"],
            check_corr=False
        )
        res = {
            "id": item["id"],
            "name": item["name"],
            "local_sharpe": round(m.sharpe, 3),
            "wq_sharpe": item["wq_sharpe"],
            "local_fitness": round(m.fitness, 3),
            "wq_fitness": item["wq_fitness"],
            "local_turnover": f"{m.turnover*100:.1f}%",
            "wq_turnover": f"{item['wq_turnover']*100:.1f}%" if item['wq_turnover'] is not None else "N/A",
            "local_runtime_ms": f"{m.runtime_ms:.1f}ms",
            "wq_status": item["wq_status"],
            "is_all_passed": m.is_all_passed(),
        }
        comparison_results.append(res)
        print(f"  -> 本地: Sharpe={m.sharpe:.2f}, Fitness={m.fitness:.2f}, TO={m.turnover*100:.1f}%, 耗时: {m.runtime_ms:.1f}ms")
    except Exception as e:
        print(f"  -> 运行失败: {e}")
        comparison_results.append({
            "id": item["id"],
            "name": item["name"],
            "error": str(e),
            "wq_sharpe": item["wq_sharpe"],
            "wq_status": item["wq_status"]
        })

output_file = Path("scratch/comparison_results.json")
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(comparison_results, f, indent=2, ensure_ascii=False)

print(f"\n对比评测已完成，结果保存至 {output_file}")
