"""
阶段二测试：Polars 向量化算子库完整性与数值正确性测试
"""

import unittest
import datetime
import numpy as np
import polars as pl
from engine import operators


class TestOperators(unittest.TestCase):
    def setUp(self):
        d1 = datetime.date(2023, 1, 1)
        d2 = datetime.date(2023, 1, 2)
        d3 = datetime.date(2023, 1, 3)

        self.df = pl.DataFrame({
            "date": [d1, d1, d1, d1, d2, d2, d2, d2, d3, d3, d3, d3],
            "ticker": ["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D"],
            "subindustry": ["Tech", "Tech", "Fin", "Fin", "Tech", "Tech", "Fin", "Fin", "Tech", "Tech", "Fin", "Fin"],
            "val": [10.0, 20.0, 30.0, 40.0, 15.0, 25.0, 35.0, 45.0, 12.0, 22.0, 32.0, 42.0],
            "val2": [2.0, 4.0, 6.0, 8.0, 3.0, 5.0, 7.0, 9.0, 2.5, 4.5, 6.5, 8.5],
        })

    def test_cross_sectional_operators(self):
        # 1. rank
        res = self.df.with_columns(r=operators.rank(pl.col("val")))
        d1_res = res.filter(pl.col("date") == datetime.date(2023, 1, 1)).sort("ticker")
        ranks = d1_res["r"].to_list()
        self.assertAlmostEqual(ranks[0], 0.0, places=3)
        self.assertAlmostEqual(ranks[3], 1.0, places=3)

        # 2. zscore
        res = self.df.with_columns(z=operators.zscore(pl.col("val")))
        d1_res = res.filter(pl.col("date") == datetime.date(2023, 1, 1))
        self.assertAlmostEqual(d1_res["z"].mean(), 0.0, places=5)

        # 3. scale
        res = self.df.with_columns(s=operators.scale(pl.col("val"), 1.0))
        d1_res = res.filter(pl.col("date") == datetime.date(2023, 1, 1))
        self.assertAlmostEqual(d1_res["s"].abs().sum(), 1.0, places=5)

        # 4. winsorize
        res = self.df.with_columns(w=operators.winsorize(pl.col("val"), 1.0))
        self.assertEqual(len(res["w"]), 12)

    def test_group_operators(self):
        # group_rank
        res = self.df.with_columns(gr=operators.group_rank(pl.col("val"), "subindustry"))
        d1_res = res.filter(pl.col("date") == datetime.date(2023, 1, 1))
        tech = d1_res.filter(pl.col("subindustry") == "Tech").sort("ticker")["gr"].to_list()
        self.assertAlmostEqual(tech[0], 0.0, places=3)
        self.assertAlmostEqual(tech[1], 1.0, places=3)

        # group_neutralize
        res = self.df.with_columns(gn=operators.group_neutralize(pl.col("val"), "subindustry"))
        d1_res = res.filter(pl.col("date") == datetime.date(2023, 1, 1))
        tech_mean = d1_res.filter(pl.col("subindustry") == "Tech")["gn"].mean()
        self.assertAlmostEqual(tech_mean, 0.0, places=5)

    def test_time_series_operators(self):
        # 1. ts_delay
        res = self.df.with_columns(d=operators.ts_delay(pl.col("val"), 1))
        stock_a = res.filter(pl.col("ticker") == "A").sort("date")
        self.assertIsNone(stock_a["d"][0])
        self.assertEqual(stock_a["d"][1], 10.0)

        # 2. ts_delta
        res = self.df.with_columns(delta=operators.ts_delta(pl.col("val"), 1))
        stock_a = res.filter(pl.col("ticker") == "A").sort("date")
        self.assertEqual(stock_a["delta"][1], 5.0)

        # 3. ts_mean & ts_std_dev
        res = self.df.with_columns([
            operators.ts_mean(pl.col("val"), 2).alias("m"),
            operators.ts_std_dev(pl.col("val"), 2).alias("s"),
        ])
        stock_a = res.filter(pl.col("ticker") == "A").sort("date")
        self.assertEqual(stock_a["m"][1], 12.5)

        # 4. ts_decay_linear
        res = self.df.with_columns(decay=operators.ts_decay_linear(pl.col("val"), 2))
        stock_a = res.filter(pl.col("ticker") == "A").sort("date")
        self.assertAlmostEqual(stock_a["decay"][1], 40.0 / 3.0, places=3)

        # 5. ts_corr
        res = self.df.with_columns(c=operators.ts_corr(pl.col("val"), pl.col("val2"), 3))
        self.assertEqual(len(res["c"]), 12)

    def test_logic_and_math_operators(self):
        # if_else
        res = self.df.with_columns(ie=operators.if_else(pl.col("val") > 25.0, 1.0, 0.0))
        self.assertEqual(res["ie"][0], 0.0)
        self.assertEqual(res["ie"][3], 1.0)

        # signed_power
        res = self.df.with_columns(sp=operators.signed_power(pl.col("val"), 0.5))
        self.assertAlmostEqual(res["sp"][0], np.sqrt(10.0), places=3)

        # trade_when
        res = self.df.with_columns(
            tw=operators.trade_when(pl.col("val") >= 15.0, pl.col("val"), default_val=-1.0)
        )
        stock_a = res.filter(pl.col("ticker") == "A").sort("date")
        self.assertEqual(stock_a["tw"][0], -1.0)
        self.assertEqual(stock_a["tw"][1], 15.0)
        self.assertEqual(stock_a["tw"][2], 15.0)


if __name__ == "__main__":
    unittest.main()
