"""
Point-in-Time 离线融合宽表构建器 (Master Dataset Builder)
将本地 pv_daily.parquet 与 fundamentals.parquet 严格按照：
- date >= filed_date (法定的正式向 SEC 递交披露的公开发布日)
- strategy="backward"
进行 As-Of Join，并在截面上生成：
- adv20: 20日均成交额
- returns: 日度收益率
- cap: 市值 (含 shares_outstanding 或基本面规模推演)
- subindustry: GICS 4 位行业分类
- is_top1000: 大市值子股票池标记 (用于 WQ Sub-Universe Check 穿透)
严格消除前视偏差，为毫秒级回测引擎提供基石。
"""

from pathlib import Path
from typing import Optional
import polars as pl
import numpy as np

from .config import (
    PV_PATH,
    FUND_PATH,
    MASTER_PATH,
    SUBINDUSTRY_MAPPING,
)


def build_master_dataset(
    pv_path: Path = PV_PATH,
    fund_path: Path = FUND_PATH,
    output_path: Path = MASTER_PATH,
    min_date: Optional[str] = "2019-01-01",
    max_date: Optional[str] = "2023-12-31",
) -> pl.DataFrame:
    print(f"[PIT Builder] 正在加载离线价量数据: {pv_path}")
    if not pv_path.exists():
        raise FileNotFoundError(f"未找到价量数据文件: {pv_path}，请先执行 download_pv.py")

    pv_df = pl.read_parquet(pv_path)
    # 日期类型转换
    if pv_df["date"].dtype != pl.Date:
        pv_df = pv_df.with_columns(pl.col("date").cast(pl.Date))

    if min_date:
        pv_df = pv_df.filter(pl.col("date") >= pl.lit(min_date).str.to_date("%Y-%m-%d"))
    if max_date:
        pv_df = pv_df.filter(pl.col("date") <= pl.lit(max_date).str.to_date("%Y-%m-%d"))

    # 检查基本面数据
    has_fundamentals = fund_path.exists()
    if has_fundamentals:
        print(f"[PIT Builder] 正在加载离线 SEC EDGAR 财报数据: {fund_path}")
        fund_df = pl.read_parquet(fund_path)
        if fund_df["filed_date"].dtype != pl.Date:
            fund_df = fund_df.with_columns(pl.col("filed_date").str.to_date("%Y-%m-%d"))
        if "end_date" in fund_df.columns and fund_df["end_date"].dtype != pl.Date:
            fund_df = fund_df.with_columns(pl.col("end_date").str.to_date("%Y-%m-%d"))

        # 按 ticker, filed_date, field 进行去重，保留同日最后披露的版本
        print("[PIT Builder] 正在按法定披露日 filed_date 透视财报长表为宽表...")
        sort_cols = ["ticker", "field", "filed_date"]
        if "end_date" in fund_df.columns:
            sort_cols.append("end_date")

        fund_dedup = fund_df.sort(sort_cols).group_by(
            ["ticker", "filed_date", "field"]
        ).last()

        # 透视成宽表
        fund_wide = fund_dedup.pivot(
            values="value",
            index=["ticker", "filed_date"],
            on="field"
        ).sort(["ticker", "filed_date"])

        # 核心 Point-in-Time 融合：使用 join_asof 严格执行 date >= filed_date
        print("[PIT Builder] 执行 Point-in-Time 严格对齐 (date >= filed_date)...")
        master = pv_df.sort("date").join_asof(
            fund_wide.sort("filed_date"),
            left_on="date",
            right_on="filed_date",
            by="ticker",
            strategy="backward"
        ).sort(["date", "ticker"])
    else:
        print("[PIT Builder] 提示: 未检测到基本面数据，仅基于价量宽表构建...")
        master = pv_df.sort(["date", "ticker"])

    # 补充 GICS 4 位行业 subindustry 映射
    print("[PIT Builder] 补充 GICS 细分行业 (subindustry) 映射...")
    tickers_in_data = master["ticker"].unique().to_list()
    subind_records = [
        {"ticker": t, "subindustry": SUBINDUSTRY_MAPPING.get(t, "Other_Industries")}
        for t in tickers_in_data
    ]
    subind_df = pl.DataFrame(subind_records)
    master = master.join(subind_df, on="ticker", how="left")

    # 确保 returns 存在
    if "returns" not in master.columns:
        master = master.with_columns(
            returns=((pl.col("close") / pl.col("close").shift(1).over("ticker")) - 1.0)
        )

    # 确保 adv20 存在
    if "adv20" not in master.columns and "volume" in master.columns:
        master = master.with_columns(
            adv20=(pl.col("close") * pl.col("volume")).rolling_mean(window_size=20, min_periods=1).over("ticker")
        )

    # 确保 cap (总市值) 存在或合理派生
    if "shares_outstanding" in master.columns:
        master = master.with_columns(
            cap=pl.when(pl.col("shares_outstanding").is_not_null() & (pl.col("shares_outstanding") > 0))
            .then(pl.col("close") * pl.col("shares_outstanding"))
            .otherwise(pl.col("close") * pl.col("adv20") * 10.0)
        )
    elif "cap" not in master.columns:
        # 基于资产/权益/成交量推导代理市值
        if "assets" in master.columns:
            master = master.with_columns(
                cap=pl.when(pl.col("assets").is_not_null() & (pl.col("assets") > 0))
                .then(pl.col("assets") * 1.5)
                .otherwise(pl.col("close") * pl.col("adv20") * 10.0)
            )
        else:
            master = master.with_columns(
                cap=pl.col("close") * pl.col("adv20") * 10.0
            )

    # 计算 is_top1000 大市值子集标签 (若总股票数不足1000，取市值前 50% 标的)
    print("[PIT Builder] 计算 is_top1000 截面标尺 (用于 Sub-Universe Check)...")
    master = master.with_columns(
        cap_rank=pl.col("cap").rank(descending=True).over("date"),
        total_stocks=pl.col("ticker").count().over("date")
    ).with_columns(
        is_top1000=pl.when(pl.col("total_stocks") >= 1000)
        .then(pl.col("cap_rank") <= 1000)
        .otherwise(pl.col("cap_rank") <= (pl.col("total_stocks") * 0.5 + 1))
    ).drop(["cap_rank", "total_stocks"])

    # 组内无未来函数前向填充 (Forward Fill) 财报科目
    exclude_cols = {"date", "ticker", "subindustry", "open", "high", "low", "close", "volume", "returns", "adv20", "cap", "is_top1000", "filed_date"}
    cols_to_fill = [c for c in master.columns if c not in exclude_cols]
    if cols_to_fill:
        print(f"[PIT Builder] 对 {len(cols_to_fill)} 个财报科目执行组内前向填充 (无前视偏差)...")
        master = master.with_columns([
            pl.col(c).forward_fill().over("ticker") for c in cols_to_fill
        ])

    # 严格检验 PIT 规则: 不允许 date < filed_date
    if "filed_date" in master.columns:
        violations = master.filter(
            pl.col("filed_date").is_not_null() & (pl.col("date") < pl.col("filed_date"))
        ).shape[0]
        assert violations == 0, f"严重警告: 发现 {violations} 条前视偏差违规记录！"
        print("[PIT Builder] 前视偏差检验通过: 0 条未来函数违规！")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.write_parquet(output_path)
    print(f"[PIT Builder] 成功构建 100% 离线、零未来函数全量宽表！")
    print(f"  维度: {master.shape[0]} 行 x {master.shape[1]} 列")
    print(f"  涵盖字段: {master.columns}")
    print(f"  持久化路径: {output_path}")
    return master


if __name__ == "__main__":
    build_master_dataset()
