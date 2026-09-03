"""
从 SEC Lakehouse 官方登记 SIC 代码极速生成全量 TOP3000 的 GICS Subindustry 行业聚类映射表
"""

import json
from pathlib import Path
import polars as pl

PROJECT_DIR = Path(__file__).resolve().parent.parent
UNIVERSE_JSON = PROJECT_DIR / "data" / "universe_top3000.json"
MAPPING_JSON = PROJECT_DIR / "data" / "ticker_subindustry_mapping.json"
LAKEHOUSE_SUB = Path(r"c:\Users\xiang\.gemini\antigravity-ide\scratch\stock_financial_crawler\sec_financial_lakehouse\sec_parquet\sub")

def sic_to_industry(sic_str) -> str:
    if not sic_str or not str(sic_str).isdigit():
        return "General_Industries"
    sic = int(sic_str)
    if 1000 <= sic <= 1499:
        return "Energy_Mining"
    elif 1500 <= sic <= 1799:
        return "Construction_Industrials"
    elif 2000 <= sic <= 2199:
        return "Consumer_Food_Beverage"
    elif 2800 <= sic <= 2836:
        return "Healthcare_Pharma"
    elif 2840 <= sic <= 2899:
        return "Materials_Chemicals"
    elif 3570 <= sic <= 3579 or 3670 <= sic <= 3679:
        return "Technology_Hardware_Semi"
    elif 3710 <= sic <= 3719:
        return "Consumer_Automotive"
    elif 3800 <= sic <= 3849:
        return "Healthcare_Instruments"
    elif 4000 <= sic <= 4799:
        return "Transportation_Logistics"
    elif 4800 <= sic <= 4899:
        return "Communications_Media"
    elif 4900 <= sic <= 4999:
        return "Utilities"
    elif 5000 <= sic <= 5199:
        return "Wholesale_Trade"
    elif 5200 <= sic <= 5999:
        return "Consumer_Discretionary_Retail"
    elif 6000 <= sic <= 6199:
        return "Financials_Banks"
    elif 6200 <= sic <= 6499:
        return "Financials_Insurance_Securities"
    elif 6500 <= sic <= 6799:
        return "Real_Estate_REITs"
    elif 7370 <= sic <= 7379:
        return "Technology_Software_Services"
    elif 8000 <= sic <= 8099:
        return "Healthcare_Services"
    else:
        return "General_Commercial_Services"

def build_mapping():
    with open(UNIVERSE_JSON, "r", encoding="utf-8") as f:
        top3000 = json.load(f)
    cik_to_ticker = {x["cik_str"]: x["ticker"] for x in top3000}
    target_ciks = set(cik_to_ticker.keys())

    sub_files = list(LAKEHOUSE_SUB.glob("*.parquet"))
    sub_df = pl.concat([
        pl.read_parquet(f, columns=["cik", "sic"]) for f in sub_files
    ]).drop_nulls().unique(subset=["cik"])

    mapping = {}
    for row in sub_df.iter_rows(named=True):
        cik = row["cik"]
        if cik in cik_to_ticker:
            ticker = cik_to_ticker[cik]
            mapping[ticker] = sic_to_industry(row["sic"])

    with open(MAPPING_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    print(f"[Industry Mapper] 成功提取并生成 {len(mapping)} 只股票的官方行业中性化分组！已保存至 {MAPPING_JSON}")

if __name__ == "__main__":
    build_mapping()
