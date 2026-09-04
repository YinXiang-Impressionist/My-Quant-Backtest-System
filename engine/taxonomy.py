# -*- coding: utf-8 -*-
"""
WorldQuant BRAIN 量化策略分类学与多层级因子特征库 (Factor Taxonomy)
================================================================================
包含 5 大类、18 个细分子类，覆盖微观量价、基本面营运、现金流真实回报、
资产负债表排雷与跨界正交双核杂交演化的全维度候选特征。
完全符合 WorldQuant 官方 100% 原生合法字段规范与无量纲闭合黄金算式。
================================================================================
"""

from typing import List, Dict, Any


def build_factor_taxonomy() -> List[Dict[str, Any]]:
    """构建多层次量化策略分类树与高质量因子特征库"""
    taxonomy = [
        # ==============================================================================
        # 第一大类：微观量价与流动性 (Micro Price-Volume & Liquidity)
        # ==============================================================================
        {
            "category": "微观量价与流动性",
            "subcategory": "1.1 VWAP 偏离与均值回归反转 (量纲严格闭合)",
            "factors": [
                {"name": "VWAP短周期偏离反转", "expr": "group_rank(ts_rank(-(close - vwap) / vwap, 20), subindustry)", "decay": 5},
                {"name": "VWAP中周期偏离反转", "expr": "group_rank(ts_rank(-(close - vwap) / vwap, 60), subindustry)", "decay": 10},
                {"name": "VWAP长周期偏离反转", "expr": "group_rank(ts_rank(-(close - vwap) / vwap, 126), subindustry)", "decay": 15},
                {"name": "VWAP偏离×成交额加权", "expr": "group_rank(ts_rank((-(close - vwap) / vwap) * (volume / (adv20 + 1000)), 60), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "微观量价与流动性",
            "subcategory": "1.2 动量与短期收益率反转",
            "factors": [
                {"name": "单日超短期收益反转", "expr": "-group_rank(returns, subindustry)", "decay": 4},
                {"name": "5日累计收益反转", "expr": "-group_rank(ts_rank(returns, 5), subindustry)", "decay": 5},
                {"name": "10日时序衰减动量反转", "expr": "-group_rank(ts_decay_linear(returns, 10), subindustry)", "decay": 5},
                {"name": "12-1月中长线跳水动量", "expr": "group_rank(ts_rank((ts_delay(close, 20) - ts_delay(close, 252)) / ts_delay(close, 252), 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "微观量价与流动性",
            "subcategory": "1.3 量价背离与换手率异动",
            "factors": [
                {"name": "10日量价相关性背离", "expr": "-group_rank(ts_corr(close, volume, 10), subindustry)", "decay": 5},
                {"name": "20日量价衰减负相关", "expr": "-group_rank(ts_decay_linear(ts_corr(close, volume, 20), 10), subindustry)", "decay": 5},
                {"name": "成交量爆发相对反转", "expr": "-group_rank(ts_rank(volume / (adv20 + 1000) * returns, 20), subindustry)", "decay": 5},
            ]
        },
        {
            "category": "微观量价与流动性",
            "subcategory": "1.4 Amihud 流动性冲击与非流动性溢价",
            "factors": [
                {"name": "Amihud 20日冲击平滑", "expr": "group_rank(ts_rank(ts_mean(abs(returns) / (volume * close + 10000), 20), 126), subindustry)", "decay": 10},
                {"name": "Amihud 60日大周期冲击", "expr": "group_rank(ts_rank(ts_mean(abs(returns) / (volume * close + 10000), 60), 252), subindustry)", "decay": 15},
                {"name": "相对换手冲击加速度", "expr": "group_rank(ts_rank(abs(returns) / (adv20 + 1000), 60), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "微观量价与流动性",
            "subcategory": "1.5 波动率与极值振幅",
            "factors": [
                {"name": "20日日内高低价振幅", "expr": "-group_rank(ts_rank((high - low) / close, 20), subindustry)", "decay": 5},
                {"name": "60日收益率时序波动率惩罚", "expr": "-group_rank(ts_std_dev(returns, 60), subindustry)", "decay": 10},
                {"name": "高低价振幅比率衰减", "expr": "-group_rank(ts_decay_linear((high - low) / (abs(returns) * close + 1.0), 20), subindustry)", "decay": 5},
            ]
        },

        # ==============================================================================
        # 第二大类：真实基本面营运与盈利质量 (Fundamental Quality & Operations)
        # ==============================================================================
        {
            "category": "真实基本面营运与盈利质量",
            "subcategory": "2.1 营业收入与资产周转利用率",
            "factors": [
                {"name": "总资产周转速度趋势", "expr": "group_rank(ts_rank(sales / assets, 126), subindustry)", "decay": 10},
                {"name": "总资产周转年化加速度", "expr": "group_rank(ts_delta(sales / assets, 252), subindustry)", "decay": 10},
                {"name": "固定资产周转营运率", "expr": "group_rank(ts_rank(sales / (capex * 4.0 + 0.01 * assets), 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "真实基本面营运与盈利质量",
            "subcategory": "2.2 净资产收益率与营业利润率趋势",
            "factors": [
                {"name": "ROE 净资产收益率时序排名", "expr": "group_rank(ts_rank(operating_income / equity, 126), subindustry)", "decay": 10},
                {"name": "ROA 总资产营业利润回报率", "expr": "group_rank(ts_rank(operating_income / assets, 126), subindustry)", "decay": 10},
                {"name": "营业利润率时序平滑", "expr": "group_rank(ts_decay_linear(operating_income / sales, 63), subindustry)", "decay": 10},
                {"name": "营业利润与市值比率 (EBIT Yield)", "expr": "group_rank(ts_rank(operating_income / cap, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "真实基本面营运与盈利质量",
            "subcategory": "2.3 毛利率改善与营业成本控制 (原生 sales - cogs)",
            "factors": [
                {"name": "毛利率水平时序趋势", "expr": "group_rank(ts_rank((sales - cogs) / sales, 126), subindustry)", "decay": 10},
                {"name": "毛利率252日时序增量", "expr": "group_rank(ts_delta((sales - cogs) / sales, 252), subindustry)", "decay": 10},
                {"name": "毛利率×资产利用率复合", "expr": "group_rank(ts_rank(((sales - cogs) / sales) * (sales / assets), 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "真实基本面营运与盈利质量",
            "subcategory": "2.4 存货积压与滞销背离排雷",
            "factors": [
                {"name": "存货年化激增排雷", "expr": "group_rank(ts_rank(-ts_delta(inventory, 252) / (cogs + 0.01 * assets), 252), subindustry)", "decay": 10},
                {"name": "存货占总资产比重缩减", "expr": "group_rank(ts_rank(-inventory / assets, 126), subindustry)", "decay": 10},
                {"name": "存货与营收变动剪刀差", "expr": "group_rank(ts_rank(-(ts_delta(inventory, 126) / assets - ts_delta(sales, 126) / assets), 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "真实基本面营运与盈利质量",
            "subcategory": "2.5 应收账款激增与操纵排雷 (DSRI)",
            "factors": [
                {"name": "应收账款激增惩罚 (DSRI)", "expr": "group_rank(ts_rank(-ts_delta(receivable, 252) / assets, 252), subindustry)", "decay": 10},
                {"name": "应收周转提速指标", "expr": "group_rank(ts_rank(sales / (receivable + 0.01 * assets), 126), subindustry)", "decay": 10},
                {"name": "应收营收剪刀差排雷", "expr": "group_rank(ts_rank(-(ts_delta(receivable, 126) / assets - ts_delta(sales, 126) / assets), 126), subindustry)", "decay": 10},
            ]
        },

        # ==============================================================================
        # 第三大类：真实现金流含金量与股东回报 (True Cash Flow & Shareholder Returns)
        # ==============================================================================
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.1 经营现金流回报率 (CFROA)",
            "factors": [
                {"name": "经营现金流总资产回报 (CFROA-半年)", "expr": "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)", "decay": 10},
                {"name": "经营现金流总资产回报 (CFROA-一年)", "expr": "group_rank(ts_rank(cashflow_op / assets, 252), subindustry)", "decay": 15},
                {"name": "经营现金流股东权益回报 (CFROE)", "expr": "group_rank(ts_rank(cashflow_op / equity, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.2 自由现金流收益率 (FCF Yield 官方语法)",
            "factors": [
                {"name": "自由现金流市值收益率 (FCF Yield)", "expr": "group_rank(ts_rank((cashflow_op - capex) / cap, 126), subindustry)", "decay": 10},
                {"name": "自由现金流企业价值回报 (FCF/EV 官方语法)", "expr": "group_rank(ts_rank((cashflow_op - capex) / (cap + debt - cash), 126), subindustry)", "decay": 10},
                {"name": "FCF / Assets 实体资产真实自由现金生成", "expr": "group_rank(ts_rank((cashflow_op - capex) / assets, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.3 利润真实性与应计盈余检验 (CFO vs Operating Income)",
            "factors": [
                {"name": "现金利润比 (CFO / Operating Income)", "expr": "group_rank(ts_rank(cashflow_op / (abs(operating_income) + 0.01 * assets), 126), subindustry)", "decay": 10},
                {"name": "应计盈余负向排雷 (Accruals Anomaly)", "expr": "group_rank(ts_rank(-(operating_income - cashflow_op) / assets, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.4 真实股票回购注销回报 (Share Buyback Yield)",
            "factors": [
                {"name": "股票回购注销市值回报 (半年)", "expr": "group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 126), subindustry)", "decay": 10},
                {"name": "股票回购注销市值回报 (一年)", "expr": "group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)", "decay": 15},
                {"name": "股票回购现金开支比", "expr": "group_rank(ts_rank(value_of_shares_reacquired_during_period / (cash + 0.01 * assets), 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.5 资本开支强度与再投资保护",
            "factors": [
                {"name": "低过度投资防御 (低 Capex/Sales)", "expr": "group_rank(ts_rank(-capex / sales, 126), subindustry)", "decay": 10},
                {"name": "现金流覆盖资本开支比率", "expr": "group_rank(ts_rank(cashflow_op / (capex + 0.01 * assets), 126), subindustry)", "decay": 10},
            ]
        },

        # ==============================================================================
        # 第四大类：资产负债表稳健性与破产排雷 (Balance Sheet & Solvency)
        # ==============================================================================
        {
            "category": "资产负债表稳健性与破产排雷",
            "subcategory": "4.1 存贷双高失真度排雷",
            "factors": [
                {"name": "存贷双高乘积排雷", "expr": "group_rank(ts_rank(-((cash / assets) * (debt / assets)), 126), subindustry)", "decay": 10},
                {"name": "现金对总负债净覆盖率", "expr": "group_rank(ts_rank((cash - debt) / assets, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "资产负债表稳健性与破产排雷",
            "subcategory": "4.2 商誉悬顶泡沫排雷",
            "factors": [
                {"name": "商誉占净资产比重排雷 (半年)", "expr": "group_rank(ts_rank(-goodwill / equity, 126), subindustry)", "decay": 10},
                {"name": "商誉占净资产比重排雷 (一年)", "expr": "group_rank(ts_rank(-goodwill / equity, 252), subindustry)", "decay": 15},
            ]
        },
        {
            "category": "资产负债表稳健性与破产排雷",
            "subcategory": "4.3 净杠杆与偿债安全垫",
            "factors": [
                {"name": "资产负债率防御 (低负债率)", "expr": "group_rank(ts_rank(equity / assets, 126), subindustry)", "decay": 10},
                {"name": "流动性安全垫 (现金占总资产)", "expr": "group_rank(ts_rank(cash / assets, 126), subindustry)", "decay": 10},
            ]
        },

        # ==============================================================================
        # 第五大类：跨界正交双核杂交进化 (Cross-Category Orthogonal Hybrids)
        # ==============================================================================
        {
            "category": "跨界正交双核杂交进化",
            "subcategory": "5.1 经营现金流 × VWAP反转控换手",
            "factors": [
                {
                    "name": "CFROA 50% × VWAP偏离反转 50%",
                    "expr": "0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.5 * group_rank(ts_rank(-(close - vwap) / vwap, 126), subindustry)",
                    "decay": 15
                },
                {
                    "name": "CFROA 35% × VWAP量比偏离 65%",
                    "expr": "0.35 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.65 * group_rank(ts_rank((-(close - vwap) / vwap) * (volume / (adv20 + 1000)), 60), subindustry)",
                    "decay": 10
                },
            ]
        },
        {
            "category": "跨界正交双核杂交进化",
            "subcategory": "5.2 自由现金流 × 股票回购 (回购权重<=25% 宏观稳健)",
            "factors": [
                {
                    "name": "FCF收益率 80% × 股票回购 20%",
                    "expr": "0.8 * group_rank(ts_rank((cashflow_op - capex) / (cap + debt - cash), 126), subindustry) + 0.2 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
                    "decay": 10
                },
                {
                    "name": "FCF收益率 75% × 股票回购 25%",
                    "expr": "0.75 * group_rank(ts_rank((cashflow_op - capex) / assets, 252), subindustry) + 0.25 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
                    "decay": 15
                },
            ]
        },
        {
            "category": "跨界正交双核杂交进化",
            "subcategory": "5.3 营运质量 × 资产负债表排雷",
            "factors": [
                {
                    "name": "营业现金流 70% × 存贷双高排雷 30%",
                    "expr": "0.7 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.3 * group_rank(ts_rank(-((cash / assets) * (debt / assets)), 126), subindustry)",
                    "decay": 10
                },
                {
                    "name": "营业现金流 70% × 商誉悬顶排雷 30%",
                    "expr": "0.7 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.3 * group_rank(ts_rank(-goodwill / equity, 252), subindustry)",
                    "decay": 10
                },
            ]
        },
        {
            "category": "跨界正交双核杂交进化",
            "subcategory": "5.4 动量反转 × 财报质量与三元增强",
            "factors": [
                {
                    "name": "5日反转 50% × CFROA现金流 50%",
                    "expr": "0.5 * -group_rank(ts_rank(returns, 5), subindustry) + 0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry)",
                    "decay": 8
                },
                {
                    "name": "VWAP反转 60% × 资产营业利润 20% × 股票回购 20% (黄金三元因子)",
                    "expr": "0.6 * group_rank(ts_decay_linear(ts_rank(-(close - vwap) / vwap, 20), 5), subindustry) + 0.2 * group_rank(ts_rank(operating_income / assets, 126), subindustry) + 0.2 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
                    "decay": 5
                }
            ]
        }
    ]
    return taxonomy
