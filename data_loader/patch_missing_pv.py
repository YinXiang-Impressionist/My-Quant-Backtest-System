"""
断点增量补全下载器：补全由于 Yahoo Finance 短暂限流跳过的剩余标的
"""

import time
import json
from pathlib import Path
import yfinance as yf
import polars as pl
import pandas as pd

from .config import DATA_DIR, PV_PATH

UNIVERSE_JSON = DATA_DIR / "universe_top3000.json"

def patch_missing():
    print("[PV Patcher] 正在检查缺失的标的列表...")
    with open(UNIVERSE_JSON, "r", encoding="utf-8") as f:
        univ = json.load(f)
    all_tickers = [x["ticker"] for x in univ]
    
    pv_df = pl.read_parquet(PV_PATH)
    existing_tickers = set(pv_df["ticker"].unique())
    
    missing_tickers = [t for t in all_tickers if t not in existing_tickers]
    print(f"[PV Patcher] 全量目标: {len(all_tickers)} 只，已有: {len(existing_tickers)} 只，待补全: {len(missing_tickers)} 只。")

    if not missing_tickers:
        print("[PV Patcher] 没有缺失标的，已为满额！")
        return

    chunk_size = 100
    new_chunks = []
    
    for i in range(0, len(missing_tickers), chunk_size):
        chunk = missing_tickers[i:i + chunk_size]
        print(f"  -> 正在补充下载第 {i+1} ~ {min(i+chunk_size, len(missing_tickers))} 只标的...")
        try:
            raw = yf.download(
                tickers=chunk,
                start="2019-01-01",
                end="2023-12-31",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    stacked = raw.stack(level=1, future_stack=True).reset_index()
                else:
                    stacked = raw.reset_index()
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
                valid_cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
                stacked = stacked[[c for c in valid_cols if c in stacked.columns]]
                stacked.dropna(subset=["close", "volume"], inplace=True)
                stacked = stacked[stacked["close"] > 0]
                if not stacked.empty:
                    new_chunks.append(pl.from_pandas(stacked))
        except Exception as e:
            print(f"  -> 下载异常: {e}")
        
        # 保护性等待 2 秒，彻底防限流
        time.sleep(2.0)

    if new_chunks:
        print(f"[PV Patcher] 正在合并补全数据并重新计算指标...")
        patch_df = pl.concat(new_chunks).sort(["ticker", "date"])
        if patch_df["date"].dtype != pl.Date:
            patch_df = patch_df.with_columns(pl.col("date").cast(pl.Date))

        patch_df = patch_df.with_columns(
            returns=((pl.col("close") / pl.col("close").shift(1).over("ticker")) - 1.0).fill_nan(0.0).fill_null(0.0),
            adv20=(pl.col("close") * pl.col("volume")).rolling_mean(window_size=20, min_samples=1).over("ticker"),
            vwap=((pl.col("high") + pl.col("low") + pl.col("close")) / 3.0)
        ).with_columns(
            cap=(pl.col("close") * pl.col("adv20") * 10.0)
        )

        full_pv = pl.concat([pv_df, patch_df]).sort(["date", "ticker"])
        full_pv.write_parquet(PV_PATH)
        print(f"[PV Patcher] 补全完成！")
        print(f"  最新总数据量: {full_pv.shape[0]:,} 行")
        print(f"  最终覆盖总股票数: {full_pv['ticker'].n_unique():,} 只！")

if __name__ == "__main__":
    patch_missing()
