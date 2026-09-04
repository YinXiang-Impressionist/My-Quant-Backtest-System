"""
WorldQuant BRAIN 本地量化回测系统 - 核心配置模块
集中管理：
1. 动态项目路径解析 (兼容任意工作区位置)
2. 美股 TOP3000 标的定义与行业 (Subindustry/Sector) 映射
3. SEC EDGAR XBRL 核心标签映射
"""

from pathlib import Path
from typing import Dict, List

# 项目根目录与数据目录
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_SEC_DIR = DATA_DIR / "raw_sec"

# 核心数据文件路径
PV_PATH = DATA_DIR / "pv_daily.parquet"
FUND_PATH = DATA_DIR / "fundamentals_top3000.parquet" if (DATA_DIR / "fundamentals_top3000.parquet").exists() else DATA_DIR / "fundamentals.parquet"
MASTER_PATH = DATA_DIR / "master_backtest.parquet"
ALIGNMENT_PATH = BASE_DIR / "data_loader" / "wq_sec_field_alignment.json"
COMMITTED_ALPHAS_PATH = DATA_DIR / "committed_alphas_pnl.parquet"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_SEC_DIR.mkdir(parents=True, exist_ok=True)

# SEC EDGAR 请求规范
SEC_HEADERS = {
    "User-Agent": "WQQuantResearch LocalEngine/2.0 (quant_researcher@mit.edu)"
}

# 核心三张表法定 XBRL 标签映射 (对齐 WorldQuant 核心字段)
XBRL_TAGS: Dict[str, List[str]] = {
    # 资产
    "assets": ["Assets"],
    "assets_curr": ["AssetsCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "cash_st": ["CashCashEquivalentsAndShortTermInvestments"],
    "receivable": ["AccountsReceivableNetCurrent", "AccountsAndOtherReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "ppent": ["PropertyPlantAndEquipmentNet"],
    "goodwill": ["Goodwill"],
    "intangible_assets": ["FiniteLivedIntangibleAssetsNet"],
    
    # 负债与权益
    "liabilities": ["Liabilities"],
    "liabilities_curr": ["LiabilitiesCurrent"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "total_debt": ["LongTermDebtNoncurrent", "LongTermDebtCurrent"],
    "debt_st": ["DebtCurrent", "ShortTermBorrowings"],
    "accounts_payable": ["AccountsPayableCurrent"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    
    # 利润表
    "operating_income": ["OperatingIncomeLoss"],
    "sales": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
    "cogs": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "gross_profit": ["GrossProfit"],
    "net_income": ["NetIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestAndDebtExpense"],
    "rd_expense": ["ResearchAndDevelopmentExpense"],
    "sga_expense": ["SellingGeneralAndAdministrativeExpense"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    
    # 现金流量表
    "cashflow_op": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cashflow_invst": ["NetCashProvidedByUsedInInvestingActivities"],
    "cashflow_fin": ["NetCashProvidedByUsedInFinancingActivities"],
    "cashflow_dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "depreciation": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"],
    
    # 股本与回购
    "shares_outstanding": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "value_of_shares_reacquired_during_period": [
        "PaymentsForRepurchaseOfCommonStock",
        "StockRepurchasedAndRetiredDuringPeriodValue",
        "TreasuryStockValueAcquiredCostMethod",
    ],
}

# GICS 行业分组映射 (WorldQuant subindustry / sector 对应聚类)
# 确保在 40 龙头成分股测试池及 TOP3000 全量扩展池中均具备充足截面深度
SUBINDUSTRY_MAPPING: Dict[str, str] = {
    # 科技组 (Technology)
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AMD": "Technology",
    "INTC": "Technology", "QCOM": "Technology", "AVGO": "Technology", "TXN": "Technology",
    "MU": "Technology", "AMAT": "Technology", "LRCX": "Technology", "ADI": "Technology",
    "ORCL": "Technology", "CRM": "Technology", "ADBE": "Technology", "NOW": "Technology",
    "INTU": "Technology", "CSCO": "Technology", "IBM": "Technology", "ACN": "Technology",
    # 互联网与传媒 (Communication)
    "GOOGL": "Communication", "GOOG": "Communication", "META": "Communication",
    "NFLX": "Communication", "DIS": "Communication", "CMCSA": "Communication",
    "VZ": "Communication", "T": "Communication",
    # 大消费与零售 (Consumer)
    "AMZN": "Consumer", "TSLA": "Consumer", "WMT": "Consumer", "COST": "Consumer",
    "HD": "Consumer", "TGT": "Consumer", "MCD": "Consumer", "SBUX": "Consumer",
    "NKE": "Consumer", "PG": "Consumer", "KO": "Consumer", "PEP": "Consumer",
    # 金融组 (Financials)
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials", "C": "Financials",
    "GS": "Financials", "MS": "Financials", "V": "Financials", "MA": "Financials",
    "AXP": "Financials", "BLK": "Financials", "BRK-B": "Financials",
    # 医疗医药 (Healthcare)
    "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare", "MRK": "Healthcare",
    "ABBV": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare", "UNH": "Healthcare",
    "ELV": "Healthcare", "TMO": "Healthcare", "DHR": "Healthcare", "ABT": "Healthcare",
    # 能源与工业制造 (Energy_Industrial)
    "XOM": "Energy_Industrial", "CVX": "Energy_Industrial", "COP": "Energy_Industrial",
    "SLB": "Energy_Industrial", "CAT": "Energy_Industrial", "DE": "Energy_Industrial",
    "GE": "Energy_Industrial", "HON": "Energy_Industrial", "UNP": "Energy_Industrial",
    "UPS": "Energy_Industrial", "RTX": "Energy_Industrial", "LMT": "Energy_Industrial",
    "BA": "Energy_Industrial", "LIN": "Energy_Industrial",
}

# 默认核心成分股池
CORE_TOP_TICKERS: List[str] = list(SUBINDUSTRY_MAPPING.keys())
