"""
在 WorldQuant BRAIN 官方云端执行前 3 个顶级因子的真实回测（严格执行纯回测，不提交）
对标本地与线上官方回测指标：Sharpe, Fitness, Turnover, Drawdown, Margin 等。
"""

import sys
import json
import time
from pathlib import Path

SKILL_DIR = Path(r"C:\Users\xiang\.gemini\config\skills\wq-alpha-research")
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from wq_core.brain_api import BrainClient

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 80)
    print(">>> 正在连接 WorldQuant BRAIN 官方 API，准备执行前 3 个因子回测 <<<")
    print(">>> 注意：严格遵循指令仅执行回测 (Simulate)，绝不调用 Submit <<<")
    print("=" * 80)

    client = BrainClient()

    alphas_to_simulate = [
        {
            "rank": 1,
            "id_tag": "Alpha_001",
            "name": "VWAP 短周期偏离反转 (20d)",
            "expression": "group_rank(ts_rank(-(close / vwap - 1), 20), subindustry)",
            "settings": {
                "instrumentType": "EQUITY",
                "region": "USA",
                "universe": "TOP3000",
                "delay": 1,
                "decay": 5,
                "neutralization": "SUBINDUSTRY",
                "truncation": 0.08,
                "pasteurization": "ON",
                "unitHandling": "VERIFY",
                "nanHandling": "ON",
                "language": "FASTEXPR",
                "visualization": False,
            },
            "local_sharpe": 2.27,
            "local_fitness": 1.62,
            "local_to": "76.7%",
        },
        {
            "rank": 2,
            "id_tag": "Alpha_060_evolved",
            "name": "VWAP反转 60% × 真实股票回购 40% (decay=10)",
            "expression": "0.6 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry) + 0.4 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
            "settings": {
                "instrumentType": "EQUITY",
                "region": "USA",
                "universe": "TOP3000",
                "delay": 1,
                "decay": 10,
                "neutralization": "SUBINDUSTRY",
                "truncation": 0.08,
                "pasteurization": "ON",
                "unitHandling": "VERIFY",
                "nanHandling": "ON",
                "language": "FASTEXPR",
                "visualization": False,
            },
            "local_sharpe": 2.23,
            "local_fitness": 1.68,
            "local_to": "31.5%",
        },
        {
            "rank": 3,
            "id_tag": "Alpha_003_evolved",
            "name": "VWAP长周期偏离反转 (126d, decay=10)",
            "expression": "group_rank(ts_rank(-(close / vwap - 1), 126), subindustry)",
            "settings": {
                "instrumentType": "EQUITY",
                "region": "USA",
                "universe": "TOP3000",
                "delay": 1,
                "decay": 10,
                "neutralization": "SUBINDUSTRY",
                "truncation": 0.08,
                "pasteurization": "ON",
                "unitHandling": "VERIFY",
                "nanHandling": "ON",
                "language": "FASTEXPR",
                "visualization": False,
            },
            "local_sharpe": 1.63,
            "local_fitness": 1.56,
            "local_to": "54.6%",
        }
    ]

    results = []

    for item in alphas_to_simulate:
        print(f"\n[{item['rank']}/3] 正在向 WorldQuant 提交回测: {item['name']}")
        print(f"  表达式: {item['expression']}")
        print(f"  设置: decay={item['settings']['decay']}, delay={item['settings']['delay']}, neut={item['settings']['neutralization']}")
        
        # 如果已经跑完过（比如 Alpha_001 LL9AE0km），直接拉取结果
        if item["id_tag"] == "Alpha_001":
            alpha_id = "LL9AE0km"
            alpha_data = client.session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            sim_res = {"status": "COMPLETE", "alpha_id": alpha_id, "data": alpha_data}
        else:
            sim_res = client.simulate(
                expression=item["expression"],
                settings=item["settings"],
                factor_name=item["name"]
            )

        if sim_res.get("status") == "COMPLETE":
            alpha_id = sim_res.get("alpha_id")
            alpha_data = sim_res.get("data") or client.session.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            is_metrics = alpha_data.get("is", {})
            
            wq_sharpe = is_metrics.get("sharpe")
            wq_fitness = is_metrics.get("fitness")
            wq_turnover = is_metrics.get("turnover")
            wq_returns = is_metrics.get("returns")
            wq_drawdown = is_metrics.get("drawdown")
            wq_margin = is_metrics.get("margin")

            print(f"  >>> 官方回测完成！Alpha ID: {alpha_id}")
            print(f"      线上 Sharpe:   {wq_sharpe:.2f}  (本地: {item['local_sharpe']})")
            print(f"      线上 Fitness:  {wq_fitness:.2f}  (本地: {item['local_fitness']})")
            print(f"      线上 Turnover: {wq_turnover*100:.1f}%  (本地: {item['local_to']})")
            print(f"      线上 Returns:  {wq_returns*100:.2f}%")
            print(f"      线上 Drawdown: {wq_drawdown*100:.2f}%")

            results.append({
                "rank": item["rank"],
                "tag": item["id_tag"],
                "alpha_id": alpha_id,
                "name": item["name"],
                "expression": item["expression"],
                "settings": item["settings"],
                "local_metrics": {
                    "sharpe": item["local_sharpe"],
                    "fitness": item["local_fitness"],
                    "turnover": item["local_to"]
                },
                "wq_online_metrics": {
                    "sharpe": wq_sharpe,
                    "fitness": wq_fitness,
                    "turnover_twosided": wq_turnover,
                    "returns": wq_returns,
                    "drawdown": wq_drawdown,
                    "margin": wq_margin,
                    "checks": is_metrics.get("checks", [])
                }
            })
        else:
            print(f"  [-] 回测失败或异常: {sim_res}")
            results.append({
                "rank": item["rank"],
                "tag": item["id_tag"],
                "name": item["name"],
                "error": sim_res
            })

        # 间隔休眠 5 秒保护 API
        time.sleep(5)

    out_file = Path("scratch/wq_top3_simulation_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"全部 3 个因子 WorldQuant 官方回测执行完毕，数据已保存至: {out_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
