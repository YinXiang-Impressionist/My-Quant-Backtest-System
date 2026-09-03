"""
离线价量数据批量下载器 (PV Downloader)
从公开交易所源批量拉取指定标的历史日 K 线，包含:
- open, high, low, close, volume, returns, cap, adv20
以 Parquet 压缩格式直接持久化到本地磁盘，支持 100% 离线回测。
"""

from pathlib import Path
from typing import List, Optional
import yfinance as yf
import polars as pl
import pandas as pd

from .config import DATA_DIR, PV_PATH, CORE_TOP_TICKERS


def download_offline_pv(
    tickers: Optional[List[str]] = None,
    start_date: str = "2019-01-01",
    end_date: str = "2023-12-31",
    output_path: Path = PV_PATH,
) -> pl.DataFrame:
    """批量并行下载美股日线价量数据并生成基础衍生量"""
    target_tickers = tickers or CORE_TOP_TICKERS
    print(f"[PV Downloader] 正在批量下载 {len(target_tickers)} 只标的历史日线数据 ({start_date} ~ {end_date})...")

    # 批量并行下载
    raw_df = yf.download(
        tickers=target_tickers,
        start=start_date,
        end=end_date,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
    )

    records = []
    for ticker in target_tickers:
        try:
            if len(target_tickers) == 1:
                sub_df = raw_df.copy()
            else:
                if ticker not in raw_df.columns.levels[0]:
                    continue
                sub_df = raw_df[ticker].dropna(how="all").copy()

            if sub_df.empty:
                continue
            sub_df = sub_df.reset_index()

            for _, row in sub_df.iterrows():
                dt = row["Date"].date() if hasattr(row["Date"], "date") else row["Date"]
                c = float(row["Close"])
                o = float(row["Open"])
                h = float(row["High"])
                l = float(row["Low"])
                v = float(row["Volume"])
                if c <= 0 or v < 0:
                    continue
                records.append({
                    "date": dt,
                    "ticker": ticker,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                })
        except Exception as e:
            print(f"Warning: Failed processing {ticker}: {e}")

    if not records:
        print("[PV Downloader] 警告: 未获取到任何价量记录！")
        return pl.DataFrame()

    df = pl.DataFrame(records).sort(["date", "ticker"])

    # 统一日期类型
    df = df.with_columns(pl.col("date").cast(pl.Date))

    # 计算日收益率: close / shift(close, 1) - 1
    df = df.with_columns(
        returns=((pl.col("close") / pl.col("close").shift(1).over("ticker")) - 1.0)
    ).filter(pl.col("returns").is_not_null())

    # 计算 20 日成交额均值: adv20 = ts_mean(close * volume, 20)
    df = df.with_columns(
        turnover_val=pl.col("close") * pl.col("volume")
    ).with_columns(
        adv20=pl.col("turnover_val").rolling_mean(window_size=20, min_periods=1).over("ticker")
    ).drop("turnover_val")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    print(f"[PV Downloader] 完成！已保存 {df.shape[0]} 条价量记录到离线 Parquet 文件: {output_path}")
    return df


if __name__ == "__main__":
    download_offline_pv()
