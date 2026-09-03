"""
离线价量数据批量下载器 (PV Downloader - Vectorized High-Speed)
从官方公开源极速拉取标的历史日 K 线，包含:
- open, high, low, close, volume, returns, cap, adv20, vwap
采用全向量化多线程下载与 Polars 并行处理，支持直接持久化至 Parquet。
"""

import time
import json
from pathlib import Path
from typing import List, Optional
import yfinance as yf
import polars as pl
import pandas as pd

from .config import DATA_DIR, PV_PATH, CORE_TOP_TICKERS

UNIVERSE_JSON = DATA_DIR / "universe_top3000.json"


def download_offline_pv(
    tickers: Optional[List[str]] = None,
    start_date: str = "2019-01-01",
    end_date: str = "2023-12-31",
    output_path: Path = PV_PATH,
    chunk_size: int = 150,
) -> pl.DataFrame:
    """批量并行下载美股日线价量数据并生成基础衍生量 (全向量化)"""
    t0 = time.time()
    
    if tickers is None:
        if UNIVERSE_JSON.exists():
            with open(UNIVERSE_JSON, "r", encoding="utf-8") as f:
                univ = json.load(f)
            target_tickers = [x["ticker"] for x in univ]
        else:
            target_tickers = CORE_TOP_TICKERS
    else:
        target_tickers = tickers

    print(f"[PV Downloader] 正在批量下载 {len(target_tickers)} 只标的日线数据 ({start_date} ~ {end_date})...")

    all_chunks = []
    
    # 分块并行拉取，防止单次请求 URL 溢出或连接超时
    for i in range(0, len(target_tickers), chunk_size):
        chunk = target_tickers[i:i + chunk_size]
        print(f"  -> 正在下载第 {i+1} ~ {min(i+chunk_size, len(target_tickers))} 只标的...")
        try:
            raw_df = yf.download(
                tickers=chunk,
                start=start_date,
                end=end_date,
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if raw_df is None or raw_df.empty:
                continue

            # 向量化转为单层 DataFrame
            if isinstance(raw_df.columns, pd.MultiIndex):
                # stack(level=1) 转平
                stacked = raw_df.stack(level=1, future_stack=True).reset_index()
            else:
                stacked = raw_df.reset_index()
                stacked["Ticker"] = chunk[0]

            stacked.rename(
                columns={
                    "Date": "date",
                    "Ticker": "ticker",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                },
                inplace=True,
            )

            # 过滤有效列
            valid_cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
            stacked = stacked[[c for c in valid_cols if c in stacked.columns]]
            stacked.dropna(subset=["close", "volume"], inplace=True)
            stacked = stacked[stacked["close"] > 0]

            if not stacked.empty:
                chunk_pl = pl.from_pandas(stacked)
                all_chunks.append(chunk_pl)
        except Exception as e:
            print(f"  -> 分块下载异常 ({i} ~ {i+chunk_size}): {e}")

    if not all_chunks:
        raise RuntimeError("未能成功下载任何标的的日线数据。")

    print("[PV Downloader] 正在合并并执行 Polars 向量化指标计算...")
    pv_df = pl.concat(all_chunks).sort(["ticker", "date"])

    # 类型标准化
    if pv_df["date"].dtype != pl.Date:
        pv_df = pv_df.with_columns(pl.col("date").cast(pl.Date))

    # 计算 returns, adv20, vwap
    pv_df = pv_df.with_columns(
        returns=((pl.col("close") / pl.col("close").shift(1).over("ticker")) - 1.0).fill_nan(0.0).fill_null(0.0),
        adv20=(pl.col("close") * pl.col("volume")).rolling_mean(window_size=20, min_samples=1).over("ticker"),
        vwap=((pl.col("high") + pl.col("low") + pl.col("close")) / 3.0)
    ).with_columns(
        # 代理估算市值 cap
        cap=(pl.col("close") * pl.col("adv20") * 10.0)
    ).sort(["date", "ticker"])

    pv_df.write_parquet(output_path)
    print(f"[PV Downloader] 下载与清洗完成！")
    print(f"  总耗时: {time.time() - t0:.2f} 秒")
    print(f"  数据规模: {pv_df.shape[0]:,} 行 x {pv_df.shape[1]} 列")
    print(f"  覆盖股票数: {pv_df['ticker'].n_unique():,} 只")
    print(f"  时间跨度: {pv_df['date'].min()} ~ {pv_df['date'].max()}")
    print(f"  已保存至: {output_path}")

    return pv_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量下载美股日线价量数据")
    parser.add_argument("--limit", type=int, default=300, help="下载前 N 大股票 (默认 300)")
    parser.add_argument("--output", type=str, default=str(PV_PATH), help="输出 Parquet 路径")
    args = parser.parse_args()

    if UNIVERSE_JSON.exists():
        with open(UNIVERSE_JSON, "r", encoding="utf-8") as f:
            univ = json.load(f)
        tickers_to_fetch = [x["ticker"] for x in univ[:args.limit]]
    else:
        tickers_to_fetch = CORE_TOP_TICKERS

    download_offline_pv(tickers=tickers_to_fetch, output_path=Path(args.output))
