"""
WorldQuant BRAIN 本地全量大规模自动化因子挖掘与层级测试系统
按 5 大类、18 个细分子类系统化测试 50+ 个 Alpha 因子，
并对接近阈值 (Sharpe > 1.0) 的潜力苗头自动执行多轮迭代进化，
输出全维度 WorldQuant IS 6 项质检达标排行榜。
"""

import sys
import json
import time
from pathlib import Path
import polars as pl

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from engine.simulator import LocalWQSimulator
from engine.correlation_checker import CorrelationChecker
from data_loader.config import MASTER_PATH

def build_factor_taxonomy():
    """构建多层次量化策略分类树"""
    taxonomy = [
        # ==============================================================================
        # 第一大类：微观量价与流动性 (Micro Price-Volume & Liquidity)
        # ==============================================================================
        {
            "category": "微观量价与流动性",
            "subcategory": "1.1 VWAP 偏离与均值回归反转",
            "factors": [
                {"name": "VWAP短周期偏离反转", "expr": "group_rank(ts_rank(-(close / vwap - 1), 20), subindustry)", "decay": 5},
                {"name": "VWAP中周期偏离反转", "expr": "group_rank(ts_rank(-(close / vwap - 1), 60), subindustry)", "decay": 10},
                {"name": "VWAP长周期偏离反转", "expr": "group_rank(ts_rank(-(close / vwap - 1), 126), subindustry)", "decay": 15},
                {"name": "VWAP偏离×成交额加权", "expr": "group_rank(ts_rank(-(close / vwap - 1) * (volume / (adv20 + 1000)), 60), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "微观量价与流动性",
            "subcategory": "1.2 动量与短期收益率反转",
            "factors": [
                {"name": "单日超短期收益反转", "expr": "-group_rank(returns, subindustry)", "decay": 4},
                {"name": "5日累计收益反转", "expr": "-group_rank(ts_rank(returns, 5), subindustry)", "decay": 5},
                {"name": "10日时序衰减动量反转", "expr": "-group_rank(ts_decay_linear(returns, 10), subindustry)", "decay": 5},
                {"name": "12-1月中长线跳水动量", "expr": "group_rank(ts_rank(ts_delay(close, 20) / ts_delay(close, 252) - 1, 126), subindustry)", "decay": 10},
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
            "subcategory": "2.3 毛利率改善与营业成本控制",
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
            "subcategory": "3.2 自由现金流收益率 (FCF Yield)",
            "factors": [
                {"name": "自由现金流市值收益率 (FCF Yield)", "expr": "group_rank(ts_rank(fcf / cap, 126), subindustry)", "decay": 10},
                {"name": "自由现金流企业价值回报 (FCF/EV)", "expr": "group_rank(ts_rank(fcf / ev, 126), subindustry)", "decay": 10},
                {"name": "FCF / Assets 实体资产真实自由现金生成", "expr": "group_rank(ts_rank(fcf / assets, 126), subindustry)", "decay": 10},
            ]
        },
        {
            "category": "现金流含金量与股东回报",
            "subcategory": "3.3 利润真实性与应计盈余检验 (CFO vs Net Income)",
            "factors": [
                {"name": "现金利润比 (CFO / Net Income)", "expr": "group_rank(ts_rank(cashflow_op / (abs(net_income) + 0.01 * assets), 126), subindustry)", "decay": 10},
                {"name": "应计盈余负向排雷 (Accruals Anomaly)", "expr": "group_rank(ts_rank(-(net_income - cashflow_op) / assets, 126), subindustry)", "decay": 10},
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
                {"name": "存贷双高乘积排雷", "expr": "group_rank(ts_rank(-((cash / assets) * (total_debt / assets)), 126), subindustry)", "decay": 10},
                {"name": "现金对总负债净覆盖率", "expr": "group_rank(ts_rank((cash - total_debt) / assets, 126), subindustry)", "decay": 10},
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
                    "expr": "0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.5 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry)",
                    "decay": 15
                },
                {
                    "name": "CFROA 35% × VWAP量比偏离 65%",
                    "expr": "0.35 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.65 * group_rank(ts_rank(-(close / vwap - 1) * (volume / (adv20 + 1000)), 60), subindustry)",
                    "decay": 10
                },
            ]
        },
        {
            "category": "跨界正交双核杂交进化",
            "subcategory": "5.2 自由现金流 × 股票回购注销",
            "factors": [
                {
                    "name": "FCF收益率 50% × 股票回购 50%",
                    "expr": "0.5 * group_rank(ts_rank(fcf / ev, 126), subindustry) + 0.5 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
                    "decay": 10
                },
                {
                    "name": "FCF收益率 35% × 股票回购 65%",
                    "expr": "0.35 * group_rank(ts_rank(fcf / ev, 252), subindustry) + 0.65 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
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
                    "expr": "0.7 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry) + 0.3 * group_rank(ts_rank(-((cash / assets) * (total_debt / assets)), 126), subindustry)",
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
            "subcategory": "5.4 动量反转 × 财报质量",
            "factors": [
                {
                    "name": "5日反转 50% × CFROA现金流 50%",
                    "expr": "0.5 * -group_rank(ts_rank(returns, 5), subindustry) + 0.5 * group_rank(ts_rank(cashflow_op / assets, 126), subindustry)",
                    "decay": 8
                },
                {
                    "name": "VWAP反转 60% × 股票回购 40%",
                    "expr": "0.6 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry) + 0.4 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)",
                    "decay": 15
                }
            ]
        }
    ]
    return taxonomy

def run_large_scale_mining():
    print("=" * 90)
    print(">>> 启动 WorldQuant BRAIN 本地全量大规模自动化因子挖掘引擎 <<<")
    print(f"当前数据集: {MASTER_PATH}")
    print("目标股票池: 3,016 只全量活跃标的 (3,458,748 行数据)")
    print("=" * 90)

    t_all_start = time.time()
    df = pl.read_parquet(MASTER_PATH)
    sim = LocalWQSimulator(df)

    taxonomy = build_factor_taxonomy()
    
    # 统计总数
    total_initial_factors = sum(len(sub["factors"]) for sub in taxonomy)
    print(f"规划策略大类: 5 大类 | 细分子类: {len(taxonomy)} 类 | 初始因子总数: {total_initial_factors} 个\n")

    all_results = []
    evolved_results = []
    qualifying_alphas = []

    tested_count = 0

    for cat_idx, sub in enumerate(taxonomy, 1):
        cat_name = sub["category"]
        sub_name = sub["subcategory"]
        print(f"\n【子类 {cat_idx}/{len(taxonomy)}】{cat_name} -> {sub_name} (包含 {len(sub['factors'])} 个因子)")
        print("-" * 90)

        for f_item in sub["factors"]:
            tested_count += 1
            f_name = f_item["name"]
            expr = f_item["expr"]
            decay = f_item.get("decay", 0)
            delay = f_item.get("delay", 1)

            t0 = time.time()
            try:
                m = sim.simulate(expr, delay=delay, decay=decay, neutralization="SUBINDUSTRY", check_corr=False)
                run_ms = (time.time() - t0) * 1000.0

                record = {
                    "id": f"Alpha_{tested_count:03d}",
                    "name": f_name,
                    "category": cat_name,
                    "subcategory": sub_name,
                    "expression": expr,
                    "decay": decay,
                    "delay": delay,
                    "sharpe": round(m.sharpe, 3),
                    "fitness": round(m.fitness, 3),
                    "turnover_twosided": round(m.turnover * 2.0, 3),
                    "returns": round(m.returns, 3),
                    "drawdown": round(m.max_drawdown, 3),
                    "sub_sharpe": round(m.sub_universe_sharpe, 3),
                    "is_all_passed": m.is_all_passed(),
                    "is_checks": m.is_checks,
                    "runtime_ms": round(run_ms, 1),
                }
                all_results.append(record)

                status_flag = "[PASS]" if m.is_all_passed() else ("[PROMIS]" if m.sharpe >= 1.0 else "[TEST]")
                print(f"[{record['id']}] {f_name[:24]:<24} | Sharpe: {m.sharpe:>6.2f} | Fitness: {m.fitness:>5.2f} | TO: {m.turnover*200:>5.1f}% | DD: {m.max_drawdown*100:>4.1f}% | {status_flag}")

                if m.is_all_passed():
                    qualifying_alphas.append(record)

                # ======================================================================
                # 自动迭代进化分支 (Auto-Evolution): 若 Sharpe >= 1.0，自动微调参数追求满贯
                # ======================================================================
                if m.sharpe >= 1.0 and not m.is_all_passed():
                    # 尝试增加平滑衰减 decay 调低换手率与回撤
                    for mut_decay in [10, 15, 20]:
                        if mut_decay == decay:
                            continue
                        m_mut = sim.simulate(expr, delay=delay, decay=mut_decay, neutralization="SUBINDUSTRY", check_corr=False)
                        if m_mut.sharpe > m.sharpe or (m_mut.sharpe >= 1.25 and m_mut.is_all_passed()):
                            mut_record = {
                                "id": f"{record['id']}_evolved",
                                "name": f"{f_name} (变异 decay={mut_decay})",
                                "category": cat_name,
                                "subcategory": sub_name,
                                "expression": expr,
                                "decay": mut_decay,
                                "delay": delay,
                                "sharpe": round(m_mut.sharpe, 3),
                                "fitness": round(m_mut.fitness, 3),
                                "turnover_twosided": round(m_mut.turnover * 2.0, 3),
                                "returns": round(m_mut.returns, 3),
                                "drawdown": round(m_mut.max_drawdown, 3),
                                "sub_sharpe": round(m_mut.sub_universe_sharpe, 3),
                                "is_all_passed": m_mut.is_all_passed(),
                                "is_checks": m_mut.is_checks,
                                "runtime_ms": round(m_mut.runtime_ms, 1),
                            }
                            evolved_results.append(mut_record)
                            all_results.append(mut_record)
                            print(f"  * [进化变异成功] decay={mut_decay} -> Sharpe: {m_mut.sharpe:.2f} | Fitness: {m_mut.fitness:.2f} | TO: {m_mut.turnover*200:.1f}%")
                            if m_mut.is_all_passed():
                                qualifying_alphas.append(mut_record)
                            break
            except Exception as e:
                print(f"  -> 回测异常: {f_name} | {e}")

    total_time = time.time() - t_all_start
    print("\n" + "=" * 90)
    print(f"大规模回测全量完成！")
    print(f"总计测试因子: {len(all_results)} 个 (含 {len(evolved_results)} 个自主变异迭代因子)")
    print(f"总耗时: {total_time:.2f} 秒 (平均单因子仅 {total_time/len(all_results)*1000:.1f} 毫秒)")
    print(f"达标高分 Alpha 数量 (满足 WorldQuant 全部红线): {len(qualifying_alphas)} 个！")
    print("=" * 90)

    # 结果持久化
    summary_path = Path("scratch/large_scale_mining_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    qualifying_path = Path("scratch/top_qualifying_alphas.json")
    with open(qualifying_path, "w", encoding="utf-8") as f:
        json.dump(qualifying_alphas, f, indent=2, ensure_ascii=False)

    print(f"所有结果已落盘至: {summary_path}")
    print(f"达标高分池已落盘至: {qualifying_path}")

if __name__ == "__main__":
    run_large_scale_mining()
