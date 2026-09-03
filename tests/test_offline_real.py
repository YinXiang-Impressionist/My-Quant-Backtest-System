"""
完全离线测试：直接加载本地磁盘 master_backtest.parquet 进行真机回测
"""

import time
import polars as pl
from pathlib import Path

from data_loader.config import MASTER_PATH
from engine.simulator import LocalWQSimulator

print(f"正在从本地磁盘读取离线数据: {MASTER_PATH}")
df = pl.read_parquet(MASTER_PATH)

print(f"数据集维度: {df.shape}")
print("包含字段:", df.columns)

simulator = LocalWQSimulator(df)

expressions = [
    ("ROE 趋势", "group_rank(ts_rank(operating_income / equity, 126), subindustry)"),
    ("总资产现金流回报率", "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)"),
    ("双核质量", "0.5 * group_rank(ts_rank(operating_income / equity, 126), subindustry) + 0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry)")
]

print("\n--- 100% 本地离线高保真回测基准测试 ---")
for name, expr in expressions:
    t0 = time.perf_counter()
    res = simulator.simulate(expr, check_corr=False)
    cost_ms = (time.perf_counter() - t0) * 1000
    print(f"\n【{name}】: {expr}")
    print(f"  回测耗时: {cost_ms:.2f} ms")
    print(f"  Sharpe: {res.sharpe} | Fitness: {res.fitness} | Turnover: {res.turnover*100:.2f}% | MaxDrawdown: {res.max_drawdown*100:.2f}%")
    print(f"  IS Checks: {res.is_checks}")
