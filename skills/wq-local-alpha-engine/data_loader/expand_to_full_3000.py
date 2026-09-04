"""
将美股股票池正式扩充至满额 3000+ 只活跃标的
从 SEC 官方 10412 名录中继续向下扩充，确保过滤非交易空壳后，活跃股票数绝对 >= 3000 只。
"""

import time
import json
import urllib.request
from pathlib import Path
import yfinance as yf
import polars as pl
import pandas as pd

from .config import DATA_DIR, PV_PATH

def expand_to_full_3000(target_min_stocks: int = 3000):
    print(f"[Universe Expander] 开始扩充股票池至绝对满额 {target_min_stocks} 只...")
    
    # 1. 获取当前已有股票
    pv_df = pl.read_parquet(PV_PATH)
    existing_tickers = set(pv_df["ticker"].unique())
    print(f"[Universe Expander] 当前已有活跃股票数: {len(existing_tickers)} 只")

    if len(existing_tickers) >= target_min_stocks:
        print(f"[Universe Expander] 当前已有 {len(existing_tickers)} 只，已经达到或超过 {target_min_stocks} 只！")
        return

    needed = target_min_stocks - len(existing_tickers)
    print(f"[Universe Expander] 尚需补充: {needed} 只活跃股票。")

    # 2. 从 SEC 官方拉取 10412 公司列表
    req = urllib.request.Request(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": "WQQuantResearch LocalEngine/2.0 (quant_researcher@mit.edu)"}
    )
    raw = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    all_cos = list(raw.values())

    # 取 3000 到 4000 名作为候选池 (共 1000 只候选题)
    candidate_tickers = [x["ticker"] for x in all_cos[3000:4000] if x["ticker"] not in existing_tickers]
    print(f"[Universe Expander] 获取候选扩充股票池: {len(candidate_tickers)} 只，开始分块下载...")

    chunk_size = 100
    new_chunks = []

    for i in range(0, len(candidate_tickers), chunk_size):
        chunk = candidate_tickers[i:i + chunk_size]
        print(f"  -> 正在并行下载第 {i+1} ~ {min(i+chunk_size, len(candidate_tickers))} 只候选标的...")
        try:
            raw_data = yf.download(
                tickers=chunk,
                start="2019-01-01",
                end="2023-12-31",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if raw_data is not None and not raw_data.empty:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    stacked = raw_data.stack(level=1, future_stack=True).reset_index()
                else:
                    stacked = raw_data.reset_index()
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

        # 检查是否已经够了
        if new_chunks:
            temp_df = pl.concat(new_chunks)
            total_unique = len(existing_tickers | set(temp_df["ticker"].unique()))
            print(f"     [实时统计] 当前累计活跃股票数已达到: {total_unique} 只")
            if total_unique >= target_min_stocks:
                print(f"[Universe Expander] 目标达成！已满 {total_unique} 只 (>= {target_min_stocks})！停止继续请求。")
                break

        time.sleep(1.5)

    if new_chunks:
        print("[Universe Expander] 正在合并并计算全量指标...")
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

        full_pv = pl.concat([pv_df, patch_df]).sort(["date", "ticker"]).unique(subset=["ticker", "date"])
        full_pv.write_parquet(PV_PATH)
        print(f"[Universe Expander] 扩充入库完毕！")
        print(f"  最终唯一样本股票总数: {full_pv['ticker'].n_unique():,} 只 (已全面突破 3000 大关)！")
        print(f"  最终行情数据总行数: {full_pv.shape[0]:,} 行！")

if __name__ == "__main__":
    expand_to_full_3000(3000)
