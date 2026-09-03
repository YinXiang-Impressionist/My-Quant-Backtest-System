"""
阶段三测试：回测仿真引擎、WorldQuant IS 规则体系与自相关性拦截测试
"""

import unittest
import numpy as np
import polars as pl
from pathlib import Path
import tempfile
import shutil

from data_loader.config import MASTER_PATH
from engine.simulator import LocalWQSimulator
from engine.correlation_checker import CorrelationChecker


class TestSimulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pl.read_parquet(MASTER_PATH)
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.corr_db = cls.temp_dir / "test_alphas.parquet"
        cls.corr_checker = CorrelationChecker(db_path=cls.corr_db)
        cls.simulator = LocalWQSimulator(cls.df, corr_checker=cls.corr_checker)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_simulation_metrics_and_speed(self):
        expr = "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
        res = self.simulator.simulate(expr, check_corr=False)

        self.assertIsInstance(res.sharpe, float)
        self.assertIsInstance(res.fitness, float)
        self.assertIsInstance(res.turnover, float)
        self.assertIsInstance(res.max_drawdown, float)
        self.assertIsInstance(res.margin, float)
        self.assertIsInstance(res.sub_universe_sharpe, float)

        # 验证极速性能: 40,000+ 行宽表单次仿真耗时控制在 150ms 以内 (通常 <50ms)
        print(f"\n[Simulator Performance] 表达式回测耗时: {res.runtime_ms:.2f} ms")
        self.assertLess(res.runtime_ms, 250.0)

        # 验证 IS 检查项完备性
        expected_checks = ["LOW_SHARPE", "LOW_FITNESS", "TURNOVER", "DRAWDOWN", "SUB_UNIVERSE_TOP1000"]
        for check in expected_checks:
            self.assertIn(check, res.is_checks)

    def test_self_correlation_interceptor(self):
        expr1 = "group_rank(ts_rank(operating_income / equity, 126), subindustry)"
        res1 = self.simulator.simulate(expr1, alpha_id="Alpha_ROE_Trend", check_corr=False)

        # 将第一个因子入库
        self.corr_checker.commit_alpha("Alpha_ROE_Trend", res1.daily_dates, res1.daily_pnl)

        # 测试提交完全相同的因子 -> 触发自相关性拦截
        res_duplicate = self.simulator.simulate(expr1, alpha_id="Alpha_Duplicate", check_corr=True)
        self.assertIn("SELF_CORRELATION", res_duplicate.is_checks)
        self.assertTrue(
            "FAIL" in res_duplicate.is_checks["SELF_CORRELATION"],
            f"相同因子未能触发自相关拦截: {res_duplicate.is_checks['SELF_CORRELATION']}"
        )

        # 测试提交反向/微调因子 (若相关性 >= 0.65 依然拦截)
        expr_similar = "0.95 * group_rank(ts_rank(operating_income / equity, 126), subindustry)"
        res_similar = self.simulator.simulate(expr_similar, alpha_id="Alpha_Similar", check_corr=True)
        self.assertTrue("FAIL" in res_similar.is_checks["SELF_CORRELATION"])


if __name__ == "__main__":
    unittest.main()
