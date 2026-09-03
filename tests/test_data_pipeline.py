"""
阶段一测试：全量 TOP3000 数据管道与 PIT 无前视偏差验证
"""

import unittest
from pathlib import Path
import polars as pl
from data_loader.config import MASTER_PATH, PV_PATH, FUND_PATH
from data_loader.build_master_dataset import build_master_dataset


class TestDataPipeline(unittest.TestCase):
    def test_paths_exist(self):
        self.assertTrue(PV_PATH.exists(), f"PV_PATH 不存在: {PV_PATH}")
        self.assertTrue(FUND_PATH.exists(), f"FUND_PATH 不存在: {FUND_PATH}")

    def test_master_dataset_structure_and_pit(self):
        df = pl.read_parquet(MASTER_PATH)
        self.assertGreater(df.shape[0], 0)
        
        # 验证核心列存在
        required_cols = [
            "date", "ticker", "close", "volume", "returns",
            "subindustry", "adv20", "cap", "is_top1000",
            "operating_income", "equity", "assets"
        ]
        for col in required_cols:
            self.assertIn(col, df.columns, f"缺少核心列: {col}")

        # 严格验证无前视偏差 (Point-in-Time)
        if "filed_date" in df.columns:
            violations = df.filter(
                pl.col("filed_date").is_not_null() & (pl.col("date") < pl.col("filed_date"))
            )
            self.assertEqual(violations.shape[0], 0, f"发现 {violations.shape[0]} 条前视偏差违规！")

        # 验证 is_top1000 数据类型与有效分布
        self.assertEqual(df["is_top1000"].dtype, pl.Boolean)
        top_counts = df["is_top1000"].value_counts()
        self.assertGreater(top_counts.filter(pl.col("is_top1000") == True)["count"][0], 0)


if __name__ == "__main__":
    unittest.main()
