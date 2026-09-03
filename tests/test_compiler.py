"""
阶段二测试：WorldQuant AST 编译器与同义词 Fallback 单元测试
"""

import unittest
import datetime
import polars as pl
from engine.expr_compiler import compile_wq_expr


class TestExprCompiler(unittest.TestCase):
    def setUp(self):
        d1 = datetime.date(2023, 1, 1)
        d2 = datetime.date(2023, 1, 2)
        self.df = pl.DataFrame({
            "date": [d1, d1, d2, d2],
            "ticker": ["A", "B", "A", "B"],
            "subindustry": ["Tech", "Tech", "Tech", "Tech"],
            "operating_income": [100.0, 200.0, 110.0, 210.0],
            "equity": [500.0, 800.0, 520.0, 810.0],
            "revenues": [1000.0, 2000.0, 1100.0, 2100.0],  # sales 的同义词
        })

    def test_basic_compilation(self):
        expr_str = "group_rank(operating_income / equity, subindustry)"
        fn = compile_wq_expr(expr_str, available_columns=set(self.df.columns))
        pl_expr = fn()
        self.assertIsInstance(pl_expr, pl.Expr)

        res = self.df.with_columns(alpha=pl_expr)
        self.assertIn("alpha", res.columns)
        self.assertEqual(len(res["alpha"]), 4)

    def test_synonym_fallback(self):
        # 表达式中使用 sales，但数据集中仅有 revenues
        expr_str = "group_rank(sales / equity, subindustry)"
        fn = compile_wq_expr(expr_str, available_columns=set(self.df.columns))
        pl_expr = fn()

        res = self.df.with_columns(alpha=pl_expr)
        self.assertIn("alpha", res.columns)
        self.assertFalse(res["alpha"].is_null().all())

    def test_complex_nested_expression(self):
        expr_str = "0.5 * group_rank(ts_decay_linear(operating_income, 2), subindustry) + 0.5 * rank(signed_power(equity, 0.5))"
        fn = compile_wq_expr(expr_str, available_columns=set(self.df.columns))

        # 执行分层管道求值
        res = fn(self.df)
        self.assertIn("raw_signal", res.columns)
        self.assertEqual(len(res["raw_signal"]), 4)


if __name__ == "__main__":
    unittest.main()
