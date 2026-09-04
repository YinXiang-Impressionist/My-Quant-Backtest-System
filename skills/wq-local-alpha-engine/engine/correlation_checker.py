"""
WorldQuant 因子库日收益自相关性前置拦截器 (Self-Correlation Checker)
功能：
1. 维护本地已提交因子库的历史日收益 (daily PnL) 矩阵；
2. 计算待测因子日收益序列与库中所有因子的 Pearson 相关系数；
3. 执行 WorldQuant 严格红线防御：max_corr >= 0.65 自动触发熔断拦截；
4. 支持达标因子一键入库持久化。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import polars as pl
import numpy as np

from data_loader.config import COMMITTED_PNL_PATH, COMMITTED_ALPHAS_PATH


class CorrelationChecker:
    """日收益相关性分析与拦截器"""

    def __init__(self, db_path: Optional[Path] = None, json_path: Optional[Path] = None):
        self.db_path = db_path or COMMITTED_PNL_PATH
        self.json_path = json_path or COMMITTED_ALPHAS_PATH
        self.alphas_df: Optional[pl.DataFrame] = None
        self._load_database()

    def _load_database(self):
        """加载已提交因子库"""
        if self.db_path.exists():
            try:
                self.alphas_df = pl.read_parquet(self.db_path)
            except Exception:
                self.alphas_df = None
        else:
            self.alphas_df = None

    def check_correlation(
        self,
        new_alpha_id: str,
        dates: List[Any],
        daily_pnl: np.ndarray,
        threshold: float = 0.65
    ) -> Tuple[bool, float, Optional[str], Dict[str, float]]:
        """
        检验新因子的日收益相关性
        返回: (is_passed, max_corr, highest_correlated_alpha, all_correlations)
        """
        if self.alphas_df is None or self.alphas_df.shape[0] == 0:
            return True, 0.0, None, {}

        # 转换为 Polars 格式进行对齐
        new_series_df = pl.DataFrame({
            "date": dates,
            new_alpha_id: daily_pnl
        }).with_columns(pl.col("date").cast(pl.Date))

        # 与库内已有因子按 date 内连接对齐
        merged = self.alphas_df.join(new_series_df, on="date", how="inner")
        if merged.shape[0] < 30:
            return True, 0.0, None, {}

        target_vals = merged[new_alpha_id].to_numpy()
        std_target = np.std(target_vals)
        if std_target < 1e-8:
            return False, 1.0, "CONSTANT_SIGNAL", {}

        existing_cols = [c for c in merged.columns if c not in ("date", new_alpha_id)]
        if not existing_cols:
            return True, 0.0, None, {}

        correlations: Dict[str, float] = {}
        max_corr = 0.0
        most_correlated = None

        for col in existing_cols:
            ref_vals = merged[col].to_numpy()
            std_ref = np.std(ref_vals)
            if std_ref > 1e-8:
                corr = float(np.corrcoef(target_vals, ref_vals)[0, 1])
                if np.isnan(corr):
                    corr = 0.0
            else:
                corr = 0.0

            abs_corr = abs(corr)
            correlations[col] = round(corr, 4)
            if abs_corr > max_corr:
                max_corr = abs_corr
                most_correlated = col

        is_passed = max_corr < threshold
        return is_passed, round(max_corr, 4), most_correlated, correlations

    def commit_alpha(
        self,
        alpha_id: str,
        dates: List[Any],
        daily_pnl: np.ndarray,
        expression: str = "",
        metrics: Optional[Any] = None
    ) -> bool:
        """将新因子加入已提交因子库并记录元数据"""
        new_df = pl.DataFrame({
            "date": dates,
            alpha_id: daily_pnl
        }).with_columns(pl.col("date").cast(pl.Date))

        if self.alphas_df is None:
            self.alphas_df = new_df
        else:
            # outer join 兼容可能不完全一致的日期区间
            self.alphas_df = self.alphas_df.join(new_df, on="date", how="full", coalesce=True).sort("date")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.alphas_df.write_parquet(self.db_path)

        # 同时记录元数据到 committed_alphas.json
        try:
            records = []
            if self.json_path.exists():
                with open(self.json_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            records.append({
                "id": alpha_id,
                "expression": expression,
                "sharpe": getattr(metrics, "sharpe", None) if metrics else None,
                "fitness": getattr(metrics, "fitness", None) if metrics else None,
                "turnover": getattr(metrics, "turnover", None) if metrics else None,
                "returns": getattr(metrics, "returns", None) if metrics else None,
                "date_committed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass

        print(f"[CorrChecker] 成功将因子 '{alpha_id}' 入库，当前工作区因子数: {len(self.alphas_df.columns) - 1}")
        return True

