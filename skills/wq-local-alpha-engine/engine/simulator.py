"""
WorldQuant 本地极速向量化多空仿真器与 IS 质检评估引擎
特性：
1. 100% 向量化 Polars 表达式执行，单次回测严格控制在 <100ms；
2. 完美对齐 WorldQuant 换手率公式：0.5 * sum(|w_t - w_{t-1}|)；
3. 严格落实 SUBINDUSTRY 截面中性化 + 0.08 极值截断 (Truncation) + 权重双边归一化；
4. 严格实施 delay=1 交易滞后防未来函数；
5. 实施 TOP1000 Sub-Universe 穿透检验与日收益 Self-Correlation 预检。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import polars as pl
import numpy as np

from .expr_compiler import compile_wq_expr
from .correlation_checker import CorrelationChecker
from . import operators


@dataclass
class AlphaMetrics:
    sharpe: float
    fitness: float
    turnover: float
    returns: float
    max_drawdown: float
    margin: float
    sub_universe_sharpe: float
    is_checks: Dict[str, str]
    daily_dates: List[Any] = field(default_factory=list)
    daily_pnl: np.ndarray = field(default_factory=lambda: np.array([]))
    runtime_ms: float = 0.0

    def is_all_passed(self) -> bool:
        """是否全部通过 WorldQuant IS 严格红线检验 (无 FAIL 阻断项)"""
        return not any("FAIL" in v for v in self.is_checks.values())


class LocalWQSimulator:
    """本地高保真 WorldQuant 回测仿真器"""

    def __init__(self, data_df: pl.DataFrame, corr_checker: Optional[CorrelationChecker] = None):
        """
        初始化仿真器
        data_df: 宽表数据，必须包含 date, ticker, subindustry, returns, is_top1000
        """
        self.df = data_df.sort(["date", "ticker"])
        self.available_columns = set(self.df.columns)
        self.corr_checker = corr_checker or CorrelationChecker()

    def simulate(
        self,
        expression: str,
        delay: int = 1,
        decay: int = 0,
        neutralization: str = "SUBINDUSTRY",
        truncation: float = 0.08,
        alpha_id: Optional[str] = None,
        check_corr: bool = True,
    ) -> AlphaMetrics:
        """执行毫秒级多空仿真回测"""
        import time
        t_start = time.perf_counter()

        # 1. AST 编译 WorldQuant 表达式
        compiled_fn = compile_wq_expr(expression, available_columns=self.available_columns)

        # 2. 批量分层向量化计算 Alpha Raw Signal
        work_df = compiled_fn(self.df)

        # 3. 截面中性化与多空权重分配
        # 仅对非 null 信号进行中性化，缺失项填充为 0.0
        if neutralization == "SUBINDUSTRY" and "subindustry" in work_df.columns:
            work_df = work_df.with_columns(
                weight=pl.when(pl.col("raw_signal").is_not_null())
                .then(operators.group_neutralize(pl.col("raw_signal"), "subindustry"))
                .otherwise(0.0)
            )
        else:
            work_df = work_df.with_columns(
                weight=pl.when(pl.col("raw_signal").is_not_null())
                .then(pl.col("raw_signal") - pl.col("raw_signal").mean().over("date"))
                .otherwise(0.0)
            )

        # 4. 截面权重缩放与 Truncation 截断
        work_df = work_df.with_columns(
            w_scaled=operators.scale(pl.col("weight"), 1.0)
        )
        # 极值截断 (默认 0.08)
        work_df = work_df.with_columns(
            w_clipped=pl.col("w_scaled").clip(-truncation, truncation)
        )
        # 再次归一化权重至 1.0 (多空绝对值之和为 1.0)
        work_df = work_df.with_columns(
            w_final=operators.scale(pl.col("w_clipped"), 1.0)
        )

        # 4.5 设定衰减 (WorldQuant settings.decay)
        if decay > 0:
            work_df = work_df.with_columns(
                w_decay=operators.ts_decay_linear(pl.col("w_final"), decay).over("ticker")
            )
            work_df = work_df.with_columns(
                w_final=operators.scale(pl.col("w_decay"), 1.0)
            )

        # 5. 计算日度持仓与 PnL (严格执行 delay 交易日生效)
        work_df = work_df.with_columns(
            pos=pl.col("w_final").shift(delay).fill_null(0.0).over("ticker")
        ).with_columns([
            (pl.col("pos") * pl.col("returns")).alias("pnl_stock"),
            (0.5 * (pl.col("pos") - pl.col("pos").shift(1).fill_null(0.0).over("ticker")).abs()).alias("to_stock"),
        ])

        # 6. 计算 Sub-Universe (TOP1000) 收益表现
        has_top1000 = "is_top1000" in work_df.columns
        if has_top1000:
            work_df = work_df.with_columns(
                sub_pnl_stock=pl.when(pl.col("is_top1000") == True).then(pl.col("pnl_stock")).otherwise(0.0)
            )

        # 7. 日度时序聚合
        agg_exprs = [
            pl.col("pnl_stock").sum().alias("daily_pnl"),
            pl.col("to_stock").sum().alias("daily_turnover"),
        ]
        if has_top1000:
            agg_exprs.append(pl.col("sub_pnl_stock").sum().alias("daily_sub_pnl"))

        daily_summary = work_df.group_by("date").agg(agg_exprs).sort("date")

        dates = daily_summary["date"].to_list()
        daily_pnls = daily_summary["daily_pnl"].to_numpy()
        daily_tos = daily_summary["daily_turnover"].to_numpy()

        # 过滤有效数据 (排除最初 delay/窗口未就绪日)
        valid_mask = (~np.isnan(daily_pnls)) & (daily_tos > 1e-6)
        if np.sum(valid_mask) < 20:
            valid_mask = ~np.isnan(daily_pnls)

        pnl = daily_pnls[valid_mask]
        to = daily_tos[valid_mask]

        runtime_ms = (time.perf_counter() - t_start) * 1000

        if len(pnl) < 20 or np.std(pnl) < 1e-8:
            return AlphaMetrics(
                sharpe=0.0,
                fitness=0.0,
                turnover=0.0,
                returns=0.0,
                max_drawdown=0.0,
                margin=0.0,
                sub_universe_sharpe=0.0,
                is_checks={"STATUS": "FAIL (Insufficient Data or Constant Signal)"},
                daily_dates=dates,
                daily_pnl=daily_pnls,
                runtime_ms=round(runtime_ms, 2),
            )

        # 8. WorldQuant 标准 IS 指标计算
        mean_pnl = float(np.mean(pnl))
        std_pnl = float(np.std(pnl))
        sharpe = float(mean_pnl / std_pnl * np.sqrt(252))
        annual_returns = float(mean_pnl * 252)
        turnover = float(np.mean(to))

        # Fitness 官方公式: Sharpe * sqrt(|Returns| / max(Turnover, 0.125))
        fitness = float(sharpe * np.sqrt(abs(annual_returns) / max(turnover, 0.125)))

        # 最大回撤 (Max Drawdown)
        cum_pnl = np.cumsum(pnl)
        cum_max = np.maximum.accumulate(cum_pnl)
        drawdowns = cum_max - cum_pnl
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Margin (基点 bps): 总收益 / 总成交金额 * 10000
        margin = float(np.sum(pnl) / (np.sum(to) + 1e-8) * 10000)

        # Sub-Universe Sharpe
        if has_top1000 and "daily_sub_pnl" in daily_summary.columns:
            sub_pnls = daily_summary["daily_sub_pnl"].to_numpy()[valid_mask]
            sub_std = np.std(sub_pnls)
            sub_sharpe = float(np.mean(sub_pnls) / sub_std * np.sqrt(252)) if sub_std > 1e-8 else 0.0
        else:
            sub_sharpe = sharpe

        # 9. IS 规则综合检验
        is_checks = {
            "LOW_SHARPE": "PASS" if sharpe >= 1.25 else f"FAIL ({sharpe:.2f} < 1.25)",
            "LOW_FITNESS": "PASS" if fitness >= 1.0 else f"FAIL ({fitness:.2f} < 1.0)",
            "TURNOVER": "PASS" if (0.01 <= turnover <= 0.70) else f"FAIL ({turnover*100:.1f}%)",
            "DRAWDOWN": "PASS" if max_dd < 0.25 else f"WARN ({max_dd*100:.1f}%)",
            "SUB_UNIVERSE_TOP1000": "PASS" if sub_sharpe >= 1.0 else f"WARN ({sub_sharpe:.2f} < 1.0)",
        }

        # 10. Self-Correlation 预检 (< 0.65 红线)
        if check_corr and self.corr_checker:
            cur_id = alpha_id or expression[:25]
            passed_corr, max_c, most_corr_id, _ = self.corr_checker.check_correlation(
                cur_id, dates, daily_pnls, threshold=0.65
            )
            if not passed_corr:
                is_checks["SELF_CORRELATION"] = f"FAIL (Max Corr: {max_c:.3f} with '{most_corr_id}')"
            else:
                is_checks["SELF_CORRELATION"] = f"PASS (Max Corr: {max_c:.3f})"

        return AlphaMetrics(
            sharpe=round(sharpe, 3),
            fitness=round(fitness, 3),
            turnover=round(turnover, 4),
            returns=round(annual_returns, 4),
            max_drawdown=round(max_dd, 4),
            margin=round(margin, 2),
            sub_universe_sharpe=round(sub_sharpe, 3),
            is_checks=is_checks,
            daily_dates=dates,
            daily_pnl=daily_pnls,
            runtime_ms=round(runtime_ms, 2),
        )
