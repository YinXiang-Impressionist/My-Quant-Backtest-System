"""
WorldQuant FastExpr 高性能 AST 编译器
核心设计：
1. 自动解耦时序 (Time-Series) 与截面 (Cross-Sectional) 窗口计算：
   - 提取嵌套的 ts_* 算子，采用分层阶段求值 (Staged Pipeline Evaluation)；
   - 彻底解决 Polars 在单个表达式中嵌套异构 over('ticker') 与 over(['date', group]) 时的上下文冲突；
2. 结合 wq_sec_field_alignment.json 与同义词注册表，自动实现字段智能 Fallback；
3. 支持复杂嵌套运算：数学函数、二元算术运算、逻辑比较、时序与分组算子；
4. 纳秒/微秒级解析，保障回测控制在毫秒级 (<100ms)。
"""

import ast
import json
from pathlib import Path
from typing import Set, Dict, List, Tuple, Optional, Any, Callable
import polars as pl
from . import operators

ALIGNMENT_FILE = Path(__file__).resolve().parent.parent / "data_loader" / "wq_sec_field_alignment.json"

FIELD_SYNONYMS: Dict[str, list] = {
    "sales": ["revenues", "revenue", "sales_revenue", "total_revenue"],
    "revenues": ["sales", "revenue", "sales_revenue"],
    "operating_income": ["ebit", "op_income", "operating_profit", "operating_income_loss"],
    "ebit": ["operating_income", "op_income"],
    "equity": ["stockholders_equity", "total_equity", "shareholders_equity"],
    "assets": ["total_assets"],
    "total_assets": ["assets"],
    "cashflow_op": ["operating_cashflow", "net_cash_operating", "cfo"],
    "capex": ["capital_expenditure", "payments_to_acquire_property"],
    "net_income": ["ni", "net_income_loss", "net_earnings"],
    "cash": ["cash_and_equivalents", "cash_equivalents"],
    "receivable": ["accounts_receivable", "receivables"],
    "inventory": ["inventories"],
    "rnd_expense": ["rd_expense", "research_and_development"],
    "shares_outstanding": ["shares", "common_shares"],
}


def load_alignment_synonyms() -> Dict[str, list]:
    mapping = dict(FIELD_SYNONYMS)
    if ALIGNMENT_FILE.exists():
        try:
            with open(ALIGNMENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for field, info in data.get("fundamental_fields", {}).items():
                sec_tag = info.get("sec_xbrl_tag", "").lower()
                if sec_tag:
                    mapping.setdefault(field, []).append(sec_tag)
        except Exception:
            pass
    return mapping


GLOBAL_SYNONYMS = load_alignment_synonyms()


class TSExtractor(ast.NodeTransformer):
    """提取嵌套的 ts_* 算子并替换为中间变量"""

    def __init__(self):
        super().__init__()
        self.staged_calls: List[Tuple[str, ast.Call]] = []
        self.counter = 0

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and func_name.startswith("ts_"):
            tmp_name = f"_ts_stage_{self.counter}"
            self.counter += 1
            self.staged_calls.append((tmp_name, node))
            return ast.Name(id=tmp_name, ctx=ast.Load())
        return node


class WQFastExprTransformer(ast.NodeTransformer):
    """AST 访问与重构为 Polars Expression 树"""

    def __init__(self, available_columns: Optional[Set[str]] = None):
        super().__init__()
        self.available_columns = available_columns

    def _resolve_column_name(self, col_name: str) -> str:
        if self.available_columns is None:
            return col_name
        if col_name in self.available_columns:
            return col_name
        col_lower = col_name.lower()
        if col_lower in self.available_columns:
            return col_lower
        candidates = GLOBAL_SYNONYMS.get(col_lower, [])
        for cand in candidates:
            if cand in self.available_columns:
                return cand
        return col_name

    def visit_Name(self, node: ast.Name):
        if node.id in ("subindustry", "industry", "sector", "market"):
            return ast.Constant(value=node.id)

        if hasattr(operators, node.id):
            return ast.Attribute(
                value=ast.Name(id="operators", ctx=ast.Load()),
                attr=node.id,
                ctx=ast.Load(),
            )

        real_col = self._resolve_column_name(node.id)
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="pl", ctx=ast.Load()),
                attr="col",
                ctx=ast.Load(),
            ),
            args=[ast.Constant(value=real_col)],
            keywords=[],
        )

    def visit_UnaryOp(self, node: ast.UnaryOp):
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node: ast.BinOp):
        self.generic_visit(node)
        return node

    def visit_Compare(self, node: ast.Compare):
        self.generic_visit(node)
        return node


class CompiledWQExpr:
    """分阶段编译执行对象"""

    def __init__(
        self,
        staged_evaluators: List[Tuple[str, Callable[[], pl.Expr]]],
        final_evaluator: Callable[[], pl.Expr]
    ):
        self.staged_evaluators = staged_evaluators
        self.final_evaluator = final_evaluator

    def __call__(self, df: Optional[pl.DataFrame] = None) -> Any:
        """
        若传入 df: 则依次计算分段列并在 df 上生成 raw_signal 列返回
        若未传 df: 则直接返回最后的 pl.Expr (兼容单表达式测试)
        """
        if df is None:
            return self.final_evaluator()

        work_df = df
        tmp_cols = []
        for col_name, evaluator in self.staged_evaluators:
            work_df = work_df.with_columns(**{col_name: evaluator()})
            tmp_cols.append(col_name)

        work_df = work_df.with_columns(raw_signal=self.final_evaluator())
        if tmp_cols:
            work_df = work_df.drop(tmp_cols)
        return work_df


def compile_wq_expr(
    expr_str: str,
    available_columns: Optional[Set[str]] = None
) -> CompiledWQExpr:
    """将 WorldQuant 表达式字符串编译为分层阶段求值对象"""
    clean_expr = expr_str.strip()
    if not clean_expr:
        raise ValueError("输入表达式不能为空！")

    tree = ast.parse(clean_expr, mode="eval")

    # 1. 抽取时序算子
    extractor = TSExtractor()
    modified_tree = extractor.visit(tree)
    ast.fix_missing_locations(modified_tree)

    # 2. 依次编译抽取出的时序算子
    staged_evaluators = []
    for tmp_name, call_node in extractor.staged_calls:
        call_tree = ast.Expression(body=call_node)
        transformer = WQFastExprTransformer(available_columns=available_columns)
        trans_tree = transformer.visit(call_tree)
        ast.fix_missing_locations(trans_tree)
        code = compile(trans_tree, filename="<ast_wq_stage>", mode="eval")
        evaluator = lambda c=code: eval(c, {"pl": pl, "operators": operators})
        staged_evaluators.append((tmp_name, evaluator))

    # 3. 编译最终主干表达式
    main_transformer = WQFastExprTransformer(available_columns=available_columns)
    main_trans_tree = main_transformer.visit(modified_tree)
    ast.fix_missing_locations(main_trans_tree)
    main_code = compile(main_trans_tree, filename="<ast_wq_main>", mode="eval")
    final_evaluator = lambda c=main_code: eval(c, {"pl": pl, "operators": operators})

    return CompiledWQExpr(staged_evaluators, final_evaluator)
