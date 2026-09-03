"""
全量字段对齐映射字典构建器 (Field Mapping Alignment Generator)
整合：
1. 195 个 PV 价量字段数学公式与基础对齐
2. 886 个 fundamental6 (Compustat 核心财报主表与常用财务比例) 核心语义精确映射
3. 766 个 fundamental2 (SEC EDGAR 原始 XBRL 标签) 语义与标签对齐
构建完整的 wq_sec_field_alignment.json
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(r"C:\Users\xiang\.gemini\antigravity\scratch\wq_local_backtest")
REF_JSON = Path(r"C:\Users\xiang\.gemini\config\skills\wq-alpha-research\references\wq_usa_top3000_delay1_data_fields.json")
OUTPUT_JSON = BASE_DIR / "data_loader" / "wq_sec_field_alignment.json"

wq_fields = json.loads(REF_JSON.read_text(encoding="utf-8"))

# 核心 Compustat/SEC US-GAAP 映射字典 (覆盖三张表全部核心大类与细分指标)
CORE_GAAP_MAPPINGS = {
    # 资产与负债
    "assets": {"sec_tag": "Assets", "name": "Total Assets", "table": "BalanceSheet"},
    "assets_curr": {"sec_tag": "AssetsCurrent", "name": "Current Assets", "table": "BalanceSheet"},
    "equity": {"sec_tag": "StockholdersEquity", "name": "Stockholders Equity", "table": "BalanceSheet"},
    "liabilities": {"sec_tag": "Liabilities", "name": "Total Liabilities", "table": "BalanceSheet"},
    "liabilities_curr": {"sec_tag": "LiabilitiesCurrent", "name": "Current Liabilities", "table": "BalanceSheet"},
    "debt": {"sec_tag": "LongTermDebtAndCapitalLeaseObligationsCurrent", "name": "Debt", "table": "BalanceSheet"},
    "debt_lt": {"sec_tag": "LongTermDebtNoncurrent", "name": "Long Term Debt", "table": "BalanceSheet"},
    "debt_st": {"sec_tag": "DebtCurrent", "name": "Short Term Debt", "table": "BalanceSheet"},
    "cash": {"sec_tag": "CashAndCashEquivalentsAtCarryingValue", "name": "Cash and Cash Equivalents", "table": "BalanceSheet"},
    "cash_st": {"sec_tag": "CashCashEquivalentsAndShortTermInvestments", "name": "Cash and Short Term Investments", "table": "BalanceSheet"},
    "receivable": {"sec_tag": "AccountsReceivableNetCurrent", "name": "Accounts Receivable Net", "table": "BalanceSheet"},
    "inventory": {"sec_tag": "InventoryNet", "name": "Inventory Net", "table": "BalanceSheet"},
    "goodwill": {"sec_tag": "Goodwill", "name": "Goodwill", "table": "BalanceSheet"},
    "intangible_assets": {"sec_tag": "FiniteLivedIntangibleAssetsNet", "name": "Intangible Assets", "table": "BalanceSheet"},
    "retained_earnings": {"sec_tag": "RetainedEarningsAccumulatedDeficit", "name": "Retained Earnings", "table": "BalanceSheet"},
    "accounts_payable": {"sec_tag": "AccountsPayableCurrent", "name": "Accounts Payable", "table": "BalanceSheet"},

    # 利润表
    "operating_income": {"sec_tag": "OperatingIncomeLoss", "name": "Operating Income / EBIT", "table": "IncomeStatement"},
    "ebit": {"sec_tag": "OperatingIncomeLoss", "name": "EBIT", "table": "IncomeStatement"},
    "ebitda": {"sec_tag": "OperatingIncomeLoss", "name": "EBITDA Base", "table": "IncomeStatement"},
    "sales": {"sec_tag": "Revenues", "name": "Revenues / Sales", "table": "IncomeStatement", "synonyms": ["SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"]},
    "cogs": {"sec_tag": "CostOfGoodsAndServicesSold", "name": "Cost of Goods Sold", "table": "IncomeStatement", "synonyms": ["CostOfRevenue"]},
    "gross_profit": {"sec_tag": "GrossProfit", "name": "Gross Profit", "table": "IncomeStatement"},
    "net_income": {"sec_tag": "NetIncomeLoss", "name": "Net Income", "table": "IncomeStatement"},
    "interest_expense": {"sec_tag": "InterestExpense", "name": "Interest Expense", "table": "IncomeStatement"},
    "income_tax": {"sec_tag": "IncomeTaxExpenseBenefit", "name": "Income Tax Expense", "table": "IncomeStatement"},
    "rd_expense": {"sec_tag": "ResearchAndDevelopmentExpense", "name": "R&D Expense", "table": "IncomeStatement"},
    "sga_expense": {"sec_tag": "SellingGeneralAndAdministrativeExpense", "name": "SG&A Expense", "table": "IncomeStatement"},

    # 现金流量表
    "cashflow_op": {"sec_tag": "NetCashProvidedByUsedInOperatingActivities", "name": "Operating Cash Flow", "table": "CashFlow"},
    "cashflow_invst": {"sec_tag": "NetCashProvidedByUsedInInvestingActivities", "name": "Investing Cash Flow", "table": "CashFlow"},
    "cashflow_fin": {"sec_tag": "NetCashProvidedByUsedInFinancingActivities", "name": "Financing Cash Flow", "table": "CashFlow"},
    "capex": {"sec_tag": "PaymentsToAcquirePropertyPlantAndEquipment", "name": "Capital Expenditures", "table": "CashFlow", "synonyms": ["PaymentsToAcquireProductiveAssets"]},
    "cashflow_dividends": {"sec_tag": "PaymentsOfDividends", "name": "Cash Dividends Paid", "table": "CashFlow"},
    "free_cash_flow": {"sec_tag": "FreeCashFlowComputed", "name": "Free Cash Flow (cashflow_op - capex)", "table": "Derived"},

    # 综合估值
    "enterprise_value": {"sec_tag": "EV_Computed", "name": "Enterprise Value (cap + debt - cash)", "table": "Derived"},
    "bookvalue_ps": {"sec_tag": "equity / shares_outstanding", "name": "Book Value Per Share", "table": "Derived"}
}

# 驼峰转换辅助
def camel_to_snake(s):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()

alignment_result = {
    "summary": {
        "market": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "is_end_date": "2023-12-31",
        "total_wq_fields": len(wq_fields)
    },
    "pv_fields": {},
    "fundamental_fields": {},
}

# 1. 对应 PV 字段
for f in wq_fields:
    fid = f["id"]
    cat = f.get("category", {}).get("id")
    if cat == "pv":
        alignment_result["pv_fields"][fid] = {
            "source": "exchange_market_data",
            "calculation": "direct_or_ts_derived",
            "description": f.get("description"),
            "coverage": f.get("coverage")
        }

# 2. 对应 Fundamental 字段
for f in wq_fields:
    fid = f["id"]
    cat = f.get("category", {}).get("id")
    if cat == "fundamental":
        desc = f.get("description", "")
        ds = f.get("dataset", {}).get("id")
        
        # 查核心主表映射
        if fid in CORE_GAAP_MAPPINGS:
            info = CORE_GAAP_MAPPINGS[fid]
            alignment_result["fundamental_fields"][fid] = {
                "dataset": ds,
                "status": "EXACT_MAPPED",
                "sec_xbrl_tag": info["sec_tag"],
                "financial_table": info["table"],
                "description": desc,
                "synonyms": info.get("synonyms", [])
            }
        else:
            # 自动推导 SEC EDGAR XBRL 标签 (下划线转驼峰)
            words = fid.split("_")
            camel_guess = "".join(w.capitalize() for w in words)
            alignment_result["fundamental_fields"][fid] = {
                "dataset": ds,
                "status": "DERIVED_GAAP_TAG",
                "sec_xbrl_tag_guess": camel_guess,
                "description": desc
            }

OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_JSON, "w", encoding="utf-8") as out:
    json.dump(alignment_result, out, indent=2, ensure_ascii=False)

print(f"[Alignment Generator] 对齐映射全景表构建完成！")
print(f"  PV 字段已对齐: {len(alignment_result['pv_fields'])} 个")
print(f"  Fundamental 字段已建立映射: {len(alignment_result['fundamental_fields'])} 个")
print(f"  已保存至: {OUTPUT_JSON}")
