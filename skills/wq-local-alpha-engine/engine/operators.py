"""
Polars 核心高性能向量化算子库
严格对齐 WorldQuant BRAIN 算子规范与数学定义：
1. 截面算子 (Cross-Sectional): rank, zscore, scale, winsorize
2. 分组算子 (Group-by-Subindustry): group_rank, group_zscore, group_neutralize
3. 时序算子 (Time-Series, 严格带 .over('ticker') 防跨股票污染):
   - ts_delay, ts_delta, ts_mean, ts_std_dev, ts_rank, ts_decay_linear
   - ts_corr, ts_zscore, ts_max, ts_min, ts_sum
4. 逻辑控制与数学函数:
   - if_else, trade_when, signed_power, log, abs, sign
"""

import polars as pl
import numpy as np
from typing import Union


# ================= 1. 截面算子 (Cross-Sectional Operators) =================

def rank(expr: pl.Expr) -> pl.Expr:
    """截面百分比排名 [0, 1]，按 date 截面执行"""
    cnt = expr.count().over("date")
    return pl.when(cnt > 1).then(
        (expr.rank(method="average").over("date") - 1.0) / (cnt - 1.0)
    ).otherwise(0.5)


def zscore(expr: pl.Expr) -> pl.Expr:
    """截面标准化 (x - mean) / std"""
    mean = expr.mean().over("date")
    std = expr.std().over("date")
    return pl.when(std > 1e-8).then((expr - mean) / std).otherwise(0.0)


def scale(expr: pl.Expr, target_sum: float = 1.0) -> pl.Expr:
    """截面缩放使绝对值之和为 target_sum (多空对称归一化)"""
    abs_sum = expr.abs().sum().over("date")
    return pl.when(abs_sum > 1e-8).then(expr * (target_sum / abs_sum)).otherwise(0.0)


def winsorize(expr: pl.Expr, std: float = 4.0) -> pl.Expr:
    """截面去极值：将偏离均值超过 std 倍标准差的异常点截断至临界值"""
    mean = expr.mean().over("date")
    std_val = expr.std().over("date")
    lower = mean - std * std_val
    upper = mean + std * std_val
    return expr.clip(lower, upper)


# ================= 2. 分组算子 (Group Operators) =================

def group_rank(expr: pl.Expr, group_col: str = "subindustry") -> pl.Expr:
    """行业/板块分组内的截面百分比排名 [0, 1]"""
    group_keys = ["date", group_col]
    cnt = expr.count().over(group_keys)
    return pl.when(cnt > 1).then(
        (expr.rank(method="average").over(group_keys) - 1.0) / (cnt - 1.0)
    ).otherwise(0.5)


def group_neutralize(expr: pl.Expr, group_col: str = "subindustry") -> pl.Expr:
    """组内均值中性化 (x - group_mean)"""
    group_keys = ["date", group_col]
    return expr - expr.mean().over(group_keys)


def group_zscore(expr: pl.Expr, group_col: str = "subindustry") -> pl.Expr:
    """组内标准化 (x - group_mean) / group_std"""
    group_keys = ["date", group_col]
    mean = expr.mean().over(group_keys)
    std = expr.std().over(group_keys)
    return pl.when(std > 1e-8).then((expr - mean) / std).otherwise(0.0)


# ================= 3. 时序算子 (Time-Series Operators) =================

def ts_delay(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滞后 d 天，按 ticker 分组"""
    return expr.shift(d).over("ticker")


def ts_delta(expr: pl.Expr, d: int) -> pl.Expr:
    """时序差分 x - ts_delay(x, d)"""
    return (expr - expr.shift(d)).over("ticker")


def ts_mean(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动均值"""
    return expr.rolling_mean(window_size=d, min_samples=max(1, d // 2)).over("ticker")


def ts_std_dev(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动标准差"""
    return expr.rolling_std(window_size=d, min_samples=max(2, d // 2)).over("ticker")


def ts_rank(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动百分比排名 [0, 1]"""
    if d <= 1:
        return pl.lit(0.5)
    r = expr.rolling_rank(window_size=d, min_samples=max(1, d // 2), method="average").over("ticker")
    return (r - 1.0) / (d - 1.0)


def ts_decay_linear(expr: pl.Expr, d: int) -> pl.Expr:
    """
    时序线性衰减加权均值
    权重 w_i = (d - i) / sum(1..d), i=0..d-1 (最新一天权重最大)
    """
    if d <= 1:
        return expr
    weights_sum = d * (d + 1) / 2.0
    # 纯 Polars 向量化表达式拼接，在 C++ 内核中极速并发执行
    weighted_expr = sum((d - i) * expr.shift(i) for i in range(d)) / weights_sum
    return weighted_expr.over("ticker")


def ts_corr(x: pl.Expr, y: pl.Expr, d: int) -> pl.Expr:
    """时序滚动 Pearson 相关系数"""
    return pl.rolling_corr(x, y, window_size=d, min_samples=max(3, d // 2)).over("ticker")


def ts_zscore(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动标准化 (x - ts_mean(x, d)) / (ts_std_dev(x, d) + 1e-8)"""
    m = expr.rolling_mean(window_size=d, min_samples=max(1, d // 2)).over("ticker")
    s = expr.rolling_std(window_size=d, min_samples=max(2, d // 2)).over("ticker")
    return pl.when(s > 1e-8).then((expr - m) / s).otherwise(0.0)


def ts_max(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动最大值"""
    return expr.rolling_max(window_size=d, min_samples=max(1, d // 2)).over("ticker")


def ts_min(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动最小值"""
    return expr.rolling_min(window_size=d, min_samples=max(1, d // 2)).over("ticker")


def ts_sum(expr: pl.Expr, d: int) -> pl.Expr:
    """时序滚动求和"""
    return expr.rolling_sum(window_size=d, min_samples=max(1, d // 2)).over("ticker")


# ================= 4. 逻辑控制与数学函数 =================

def if_else(condition: pl.Expr, true_expr: Union[pl.Expr, float, int], false_expr: Union[pl.Expr, float, int]) -> pl.Expr:
    """三元条件逻辑"""
    return pl.when(condition).then(true_expr).otherwise(false_expr)


def trade_when(condition: pl.Expr, alpha: pl.Expr, default_val: float = -1.0) -> pl.Expr:
    """
    WorldQuant 经典条件触发持仓：
    当 condition 为真时更新为 alpha 信号，否则保持前一交易日信号 (forward_fill)，初值填充 default_val
    """
    signal = pl.when(condition).then(alpha).otherwise(None)
    return signal.forward_fill().fill_null(default_val).over("ticker")


def signed_power(expr: pl.Expr, p: float) -> pl.Expr:
    """保持符号的幂运算: sign(x) * |x|^p"""
    return expr.sign() * (expr.abs() ** p)


def log(expr: pl.Expr) -> pl.Expr:
    """自然对数 (自动防护非正数)"""
    return pl.when(expr > 1e-8).then(expr.log()).otherwise(None)


def abs(expr: pl.Expr) -> pl.Expr:
    """绝对值"""
    return expr.abs()


def sign(expr: pl.Expr) -> pl.Expr:
    """符号函数: 1.0, 0.0, -1.0"""
    return expr.sign()
