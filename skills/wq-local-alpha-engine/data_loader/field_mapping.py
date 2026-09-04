"""
WorldQuant BRAIN 字段映射字典与规范定义
包含：
1. 基础价量 (PV) 映射规则
2. SEC EDGAR XBRL 核心三张表基本面 (Fundamentals) 映射规则
3. 分析师一致预期 (Analyst) 映射规则
4. PIT (Point-in-Time) 对齐规则
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FieldMapping:
    wq_field: str               # WorldQuant 字段名
    category: str               # pv, fundamental, analyst, industry
    source: str                 # yfinance, sec_edgar, finnhub, gics
    source_metric: str          # 数据源原生指标名/XBRL Tag
    description: str            # 描述与说明
    is_pit_required: bool = False # 是否必须严格 Point-in-Time 披露日对齐
    unit_converter: Optional[str] = None # 单位换算


# 核心映射注册表
FIELD_MAPPINGS: Dict[str, FieldMapping] = {
    # ---------------- 1. 价量 (PV) ----------------
    "close": FieldMapping(
        wq_field="close",
        category="pv",
        source="yfinance",
        source_metric="Close",
        description="收盘价 (复权/不复权根据设定切换)",
    ),
    "open": FieldMapping(
        wq_field="open",
        category="pv",
        source="yfinance",
        source_metric="Open",
        description="开盘价",
    ),
    "high": FieldMapping(
        wq_field="high",
        category="pv",
        source="yfinance",
        source_metric="High",
        description="最高价",
    ),
    "low": FieldMapping(
        wq_field="low",
        category="pv",
        source="yfinance",
        source_metric="Low",
        description="最低价",
    ),
    "volume": FieldMapping(
        wq_field="volume",
        category="pv",
        source="yfinance",
        source_metric="Volume",
        description="成交量 (股)",
    ),
    "returns": FieldMapping(
        wq_field="returns",
        category="pv",
        source="yfinance",
        source_metric="close.pct_change()",
        description="日度收益率 (Close / PrevClose - 1)",
    ),
    "cap": FieldMapping(
        wq_field="cap",
        category="pv",
        source="yfinance_sec",
        source_metric="close * shares_outstanding",
        description="总市值 (Market Capitalization)",
    ),
    "adv20": FieldMapping(
        wq_field="adv20",
        category="pv",
        source="computed",
        source_metric="ts_mean(close * volume, 20)",
        description="20日日均成交额 (Average Daily Volume)",
    ),

    # ---------------- 2. 核心三张表基本面 (Fundamentals - SEC EDGAR XBRL) ----------------
    "operating_income": FieldMapping(
        wq_field="operating_income",
        category="fundamental",
        source="sec_edgar",
        source_metric="OperatingIncomeLoss",
        description="营业利润 (Operating Income / EBIT)",
        is_pit_required=True,
    ),
    "sales": FieldMapping(
        wq_field="sales",
        category="fundamental",
        source="sec_edgar",
        source_metric="Revenues | SalesRevenueNet",
        description="营业总收入 (Revenue / Sales)",
        is_pit_required=True,
    ),
    "cogs": FieldMapping(
        wq_field="cogs",
        category="fundamental",
        source="sec_edgar",
        source_metric="CostOfGoodsAndServicesSold | CostOfRevenue",
        description="营业成本 (Cost of Goods Sold)",
        is_pit_required=True,
    ),
    "net_income": FieldMapping(
        wq_field="net_income",
        category="fundamental",
        source="sec_edgar",
        source_metric="NetIncomeLoss",
        description="净利润 (Net Income)",
        is_pit_required=True,
    ),
    "assets": FieldMapping(
        wq_field="assets",
        category="fundamental",
        source="sec_edgar",
        source_metric="Assets",
        description="总资产 (Total Assets)",
        is_pit_required=True,
    ),
    "equity": FieldMapping(
        wq_field="equity",
        category="fundamental",
        source="sec_edgar",
        source_metric="StockholdersEquity",
        description="股东权益 / 净资产 (Total Stockholders Equity)",
        is_pit_required=True,
    ),
    "debt": FieldMapping(
        wq_field="debt",
        category="fundamental",
        source="sec_edgar",
        source_metric="LongTermDebtAndCapitalLeaseObligationsCurrent + LongTermDebtNoncurrent",
        description="总债务 (Total Debt)",
        is_pit_required=True,
    ),
    "cash": FieldMapping(
        wq_field="cash",
        category="fundamental",
        source="sec_edgar",
        source_metric="CashAndCashEquivalentsAtCarryingValue",
        description="现金及现金等价物",
        is_pit_required=True,
    ),
    "receivable": FieldMapping(
        wq_field="receivable",
        category="fundamental",
        source="sec_edgar",
        source_metric="AccountsReceivableNetCurrent",
        description="应收账款 (Accounts Receivable Net)",
        is_pit_required=True,
    ),
    "inventory": FieldMapping(
        wq_field="inventory",
        category="fundamental",
        source="sec_edgar",
        source_metric="InventoryNet",
        description="存货 (Inventories Net)",
        is_pit_required=True,
    ),
    "cashflow_op": FieldMapping(
        wq_field="cashflow_op",
        category="fundamental",
        source="sec_edgar",
        source_metric="NetCashProvidedByUsedInOperatingActivities",
        description="经营活动现金流净额 (Operating Cash Flow)",
        is_pit_required=True,
    ),
    "capex": FieldMapping(
        wq_field="capex",
        category="fundamental",
        source="sec_edgar",
        source_metric="PaymentsToAcquirePropertyPlantAndEquipment",
        description="资本性支出 (Capital Expenditures)",
        is_pit_required=True,
    ),
    "enterprise_value": FieldMapping(
        wq_field="enterprise_value",
        category="fundamental",
        source="computed",
        source_metric="cap + debt - cash",
        description="企业价值 (Enterprise Value: EV)",
        is_pit_required=True,
    ),

    # ---------------- 3. 分析师预期 (Analyst) ----------------
    "est_eps": FieldMapping(
        wq_field="est_eps",
        category="analyst",
        source="finnhub",
        source_metric="epsEstimate",
        description="分析师一致预期 EPS (Consensus EPS Estimate)",
        is_pit_required=True,
    ),

    # ---------------- 4. 行业与细分行业 (Industry) ----------------
    "subindustry": FieldMapping(
        wq_field="subindustry",
        category="industry",
        source="gics_sic",
        source_metric="GICS_SubIndustry | SIC_4Digit",
        description="细分子行业 (WorldQuant 核心 group_rank 分组字段)",
    ),
    "industry": FieldMapping(
        wq_field="industry",
        category="industry",
        source="gics_sic",
        source_metric="GICS_Industry | SIC_3Digit",
        description="一级行业",
    ),
    "sector": FieldMapping(
        wq_field="sector",
        category="industry",
        source="gics_sic",
        source_metric="GICS_Sector | SIC_2Digit",
        description="大类板块",
    ),
}


def get_field_info(field_name: str) -> Optional[FieldMapping]:
    return FIELD_MAPPINGS.get(field_name.lower())
