import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("scratch/large_scale_mining_results.json", "r", encoding="utf-8") as f:
    res = json.load(f)

sorted_alphas = sorted(res, key=lambda x: x["sharpe"], reverse=True)

print("=" * 105)
print(f"{'排名':<4} | {'ID':<18} | {'因子名称':<32} | {'Sharpe':<8} | {'Fitness':<8} | {'双边TO':<8} | {'最大DD':<8} | 细分子类")
print("=" * 105)

for i, a in enumerate(sorted_alphas[:25], 1):
    print(f"{i:<4} | {a['id']:<18} | {a['name'][:30]:<32} | {a['sharpe']:>6.2f} | {a['fitness']:>6.2f} | {a['turnover_twosided']*100:>6.1f}% | {a['drawdown']*100:>6.1f}% | {a['subcategory']}")

print("=" * 105)
