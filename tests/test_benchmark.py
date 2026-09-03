import datetime
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import numpy as np
import polars as pl
from data_loader.config import MASTER_PATH
from engine.simulator import LocalWQSimulator

print("Generating mock TOP3000 dataset for verification...")
num_dates = 252  # 1 年
num_tickers = 500  # 500 只股票
np.random.seed(42)

dates = [datetime.date(2023, 1, 1) + datetime.timedelta(days=i) for i in range(num_dates)]
tickers = [f"US_{i:04d}" for i in range(num_tickers)]
subindustries = [f"SubInd_{i % 20}" for i in range(num_tickers)]

data = []
for d in dates:
    ret_factor = np.random.normal(0.0003, 0.015, size=num_tickers)
    oi = np.random.exponential(100.0, size=num_tickers)
    eq = np.random.exponential(500.0, size=num_tickers) + 10.0
    cf = np.random.exponential(80.0, size=num_tickers)
    eps = np.random.normal(2.0, 1.0, size=num_tickers)
    close = np.random.uniform(10.0, 200.0, size=num_tickers)

    for i in range(num_tickers):
        data.append({
            "date": d,
            "ticker": tickers[i],
            "subindustry": subindustries[i],
            "returns": float(ret_factor[i]),
            "operating_income": float(oi[i]),
            "equity": float(eq[i]),
            "cashflow_op": float(cf[i]),
            "est_eps": float(eps[i]),
            "close": float(close[i]),
            "is_top1000": (i < 250),
        })

df = pl.DataFrame(data).sort(["date", "ticker"])
print(f"Dataframe created with {df.shape[0]} rows, {df.shape[1]} columns.")

simulator = LocalWQSimulator(df)

test_exprs = [
    "group_rank(ts_rank(operating_income / equity, 126), subindustry)",
    "0.5 * group_rank(ts_rank(operating_income / equity, 126), subindustry) + 0.5 * group_rank(ts_rank(cashflow_op / equity, 126), subindustry)",
    "group_rank(ts_rank(est_eps / close, 126), subindustry)"
]

print("\n--- Running Ultra-Fast Simulation Benchmark ---")
for expr in test_exprs:
    t0 = time.perf_counter()
    metrics = simulator.simulate(expr, check_corr=False)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"\nExpression: {expr}")
    print(f"Speed: {elapsed:.2f} ms")
    print(f"Metrics: Sharpe={metrics.sharpe}, Fitness={metrics.fitness}, TO={metrics.turnover*100:.1f}%, Returns={metrics.returns*100:.2f}%, Drawdown={metrics.max_drawdown*100:.2f}%")
    print(f"IS Checks: {metrics.is_checks}")
