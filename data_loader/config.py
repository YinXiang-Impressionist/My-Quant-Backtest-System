"""
WorldQuant BRAIN 本地量化回测系统 - 核心配置模块
集中管理：
1. 动态项目路径解析 (兼容任意工作区位置)
2. 美股 TOP3000 标的定义与行业 (Subindustry/Sector) 映射
3. SEC EDGAR XBRL 核心标签映射
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

# 1. 代码模块根目录 (代码与只读资产所在位置)
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. 用户当前工作目录 (运行产生的日志与持久化记录强制落盘于此)
WORKSPACE_DIR = Path.cwd()
LOGS_DIR = WORKSPACE_DIR / "logs"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"
COMMITTED_DIR = WORKSPACE_DIR / "data"

# 本地工作区持久化文件
COMMITTED_ALPHAS_PATH = COMMITTED_DIR / "committed_alphas.json"
COMMITTED_PNL_PATH = COMMITTED_DIR / "committed_alphas_pnl.parquet"
SUBMISSIONS_DIR = COMMITTED_DIR / "submissions"


def ensure_workspace_dirs():
    """按需就地初始化当前工作目录的记录子文件夹"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    COMMITTED_DIR.mkdir(parents=True, exist_ok=True)
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)


# 3. 智能解析 59 维 Lakehouse 宽表数据源 (只读)
def resolve_master_path() -> Path:
    # 1. 优先支持环境变量 (方便 CI/CD 或容器自定义指定)
    env_path = os.getenv("WQ_MASTER_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path).resolve()

    # 2. 自适应探测路径 (当前工作目录、当前模块根目录、同级兄弟工程目录及全局技能库)
    candidates = [
        WORKSPACE_DIR / "data" / "master_backtest.parquet",
        BASE_DIR / "data" / "master_backtest.parquet",
    ]

    # 自动探测同级兄弟工程目录
    if BASE_DIR.parent.exists():
        for sibling in BASE_DIR.parent.iterdir():
            if sibling.is_dir() and sibling != BASE_DIR:
                candidates.append(sibling / "data" / "master_backtest.parquet")

    # 全局技能库备选探测
    candidates.append(Path.home() / ".gemini" / "config" / "skills" / "wq-local-alpha-engine" / "data" / "master_backtest.parquet")

    for p in candidates:
        if p.exists():
            return p.resolve()
    return (BASE_DIR / "data" / "master_backtest.parquet").resolve()


MASTER_PATH = resolve_master_path()
DATA_DIR = MASTER_PATH.parent
RAW_SEC_DIR = DATA_DIR / "raw_sec"

PV_PATH = DATA_DIR / "pv_daily.parquet"
FUND_PATH = DATA_DIR / "fundamentals_top3000.parquet" if (DATA_DIR / "fundamentals_top3000.parquet").exists() else DATA_DIR / "fundamentals.parquet"

# 对齐字典路径 (完全动态探测)
ALIGNMENT_PATH = BASE_DIR / "data_loader" / "wq_sec_field_alignment.json"
if not ALIGNMENT_PATH.exists():
    align_candidates = [
        WORKSPACE_DIR / "data_loader" / "wq_sec_field_alignment.json",
    ]
    if BASE_DIR.parent.exists():
        for sibling in BASE_DIR.parent.iterdir():
            if sibling.is_dir() and sibling != BASE_DIR:
                align_candidates.append(sibling / "data_loader" / "wq_sec_field_alignment.json")
    align_candidates.append(Path.home() / ".gemini" / "config" / "skills" / "wq-local-alpha-engine" / "data_loader" / "wq_sec_field_alignment.json")

    for cand in align_candidates:
        if cand.exists():
            ALIGNMENT_PATH = cand.resolve()
            break


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
