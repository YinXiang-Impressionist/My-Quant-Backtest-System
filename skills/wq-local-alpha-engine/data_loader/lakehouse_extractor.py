"""
SEC Financial Lakehouse Extractor for WorldQuant TOP3000 Universe
从本地现有的 sec_financial_lakehouse (42个季度的SEC全量财报Parquet) 中，
极速提取 2019-2023 年 USA TOP3000 全部成分股的核心财务特征，
严格按照法定披露日 filed_date 生成无前视偏差的 fundamentals_top3000.parquet。
"""

import time
import json
from pathlib import Path
import polars as pl

# 1. 路径定位
PROJECT_DIR = Path(__file__).resolve().parent.parent
LAKEHOUSE_DIR = Path(r"c:\Users\xiang\.gemini\antigravity-ide\scratch\stock_financial_crawler\sec_financial_lakehouse\sec_parquet")
UNIVERSE_JSON = PROJECT_DIR / "data" / "universe_top3000.json"
OUTPUT_PARQUET = PROJECT_DIR / "data" / "fundamentals_top3000.parquet"

# 2. 目标财报标签映射 (全面对齐 WorldQuant 核心三张表会计科目)
TAG_TO_FIELD = {
    # 资产类
    "Assets": "assets",
    "AssetsCurrent": "assets_curr",
    "CashAndCashEquivalentsAtCarryingValue": "cash",
    "CashCashEquivalentsAndShortTermInvestments": "cash_st",
    "AccountsReceivableNetCurrent": "receivable",
    "AccountsAndOtherReceivablesNetCurrent": "receivable",
    "InventoryNet": "inventory",
    "PropertyPlantAndEquipmentNet": "ppent",
    "Goodwill": "goodwill",
    "FiniteLivedIntangibleAssetsNet": "intangible_assets",

    # 负债与股东权益
    "Liabilities": "liabilities",
    "LiabilitiesCurrent": "liabilities_curr",
    "StockholdersEquity": "equity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "equity",
    "LongTermDebtNoncurrent": "total_debt",
    "LongTermDebtCurrent": "debt_st",
    "DebtCurrent": "debt_st",
    "ShortTermBorrowings": "debt_st",
    "AccountsPayableCurrent": "accounts_payable",
    "RetainedEarningsAccumulatedDeficit": "retained_earnings",

    # 利润表
    "OperatingIncomeLoss": "operating_income",
    "Revenues": "sales",
    "SalesRevenueNet": "sales",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "sales",
    "CostOfGoodsAndServicesSold": "cogs",
    "CostOfRevenue": "cogs",
    "GrossProfit": "gross_profit",
    "NetIncomeLoss": "net_income",
    "InterestExpense": "interest_expense",
    "InterestAndDebtExpense": "interest_expense",
    "ResearchAndDevelopmentExpense": "rd_expense",
    "SellingGeneralAndAdministrativeExpense": "sga_expense",
    "IncomeTaxExpenseBenefit": "income_tax",

    # 现金流量表
    "NetCashProvidedByUsedInOperatingActivities": "cashflow_op",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "PaymentsToAcquireProductiveAssets": "capex",
    "NetCashProvidedByUsedInInvestingActivities": "cashflow_invst",
    "NetCashProvidedByUsedInFinancingActivities": "cashflow_fin",
    "PaymentsOfDividends": "cashflow_dividends",
    "PaymentsOfDividendsCommonStock": "cashflow_dividends",
    "DepreciationDepletionAndAmortization": "depreciation",
    "DepreciationAndAmortization": "depreciation",
    "Depreciation": "depreciation",

    # 股本与股票回购
    "CommonStockSharesOutstanding": "shares_outstanding",
    "EntityCommonStockSharesOutstanding": "shares_outstanding",
    "PaymentsForRepurchaseOfCommonStock": "value_of_shares_reacquired_during_period",
    "StockRepurchasedAndRetiredDuringPeriodValue": "value_of_shares_reacquired_during_period",
}

def extract_lakehouse_top3000():
    t0 = time.time()
    print("[Lakehouse Extractor] 开始从本地 SEC Lakehouse 极速提取 TOP3000 财报特征...")

    # 读取 TOP3000 映射
    with open(UNIVERSE_JSON, "r", encoding="utf-8") as f:
        universe = json.load(f)
    
    cik_to_ticker = {item["cik_str"]: item["ticker"] for item in universe}
    target_ciks = set(cik_to_ticker.keys())
    print(f"[Lakehouse Extractor] 已加载 TOP3000 股票池，共 {len(target_ciks)} 个目标 CIK。")

    target_tags = set(TAG_TO_FIELD.keys())

    # 季度清单 (2019Q1 ~ 2023Q4, 共 20 季度)
    quarters = [f"20{y}q{q}" for y in range(19, 24) for q in range(1, 5)]
    
    records = []

    for q in quarters:
        sub_path = LAKEHOUSE_DIR / "sub" / f"{q}.parquet"
        num_path = LAKEHOUSE_DIR / "num" / f"{q}.parquet"

        if not sub_path.exists() or not num_path.exists():
            continue

        # 1. 过滤目标 CIK 的提交记录 (sub)
        sub_df = pl.read_parquet(
            sub_path,
            columns=["adsh", "cik", "filed", "form", "sic"]
        ).filter(
            pl.col("cik").is_in(target_ciks) & pl.col("form").is_in(["10-K", "10-Q", "10-K/A", "10-Q/A"])
        )

        if sub_df.shape[0] == 0:
            continue

        # 2. 过滤数字指标记录 (num)
        # 注意: ddate 代表期末截止日，qtrs 为 0/1/4
        num_df = pl.read_parquet(
            num_path,
            columns=["adsh", "tag", "ddate", "value"]
        ).filter(
            pl.col("tag").is_in(target_tags)
        )

        # 关联 sub 与 num
        merged = sub_df.join(num_df, on="adsh", how="inner")

        if merged.shape[0] > 0:
            records.append(merged)

    if not records:
        print("[Lakehouse Extractor] 未提取到数据！")
        return

    print(f"[Lakehouse Extractor] 正在合并 {len(records)} 个季度的原始数据...")
    full_df = pl.concat(records)

    # 字段转换与映射
    print("[Lakehouse Extractor] 正在转换为标准字段体系与日期格式...")
    # 将 filed YYYYMMDD 转为 Date
    full_df = full_df.with_columns(
        filed_date=pl.col("filed").cast(pl.String).str.to_date("%Y%m%d"),
        field=pl.col("tag").replace(TAG_TO_FIELD),
        ticker=pl.col("cik").replace(cik_to_ticker, default=None)
    ).filter(
        pl.col("ticker").is_not_null() & pl.col("filed_date").is_not_null()
    )

    # 聚合去重：按 ticker, filed_date, field 取最后一条
    print("[Lakehouse Extractor] 执行去重与清洗...")
    dedup_df = full_df.group_by(["ticker", "filed_date", "field"]).last()

    # 转换为宽表 (按 ticker, filed_date 透视)
    print("[Lakehouse Extractor] 透视长表为标准 Point-in-Time 宽表...")
    wide_df = dedup_df.pivot(
        values="value",
        index=["ticker", "filed_date"],
        on="field"
    ).sort(["ticker", "filed_date"])

    wide_df.write_parquet(OUTPUT_PARQUET)
    print(f"[Lakehouse Extractor] 提取完成！")
    print(f"  耗时: {time.time() - t0:.2f} 秒")
    print(f"  宽表维度: {wide_df.shape[0]:,} 行 x {wide_df.shape[1]} 列")
    print(f"  涵盖股票数: {wide_df['ticker'].n_unique():,} 只")
    print(f"  文件已保存至: {OUTPUT_PARQUET}")

if __name__ == "__main__":
    extract_lakehouse_top3000()
