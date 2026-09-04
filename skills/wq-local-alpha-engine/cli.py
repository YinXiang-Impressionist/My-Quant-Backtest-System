"""
WorldQuant BRAIN 本地超快速量化回测与因子初筛引擎 - 统一命令行工具 (CLI)
用法：
1. 单因子极速回测与富文本诊断：
   python -m cli run --expr "group_rank(ts_rank(operating_income / equity, 126), subindustry)"

2. 批量因子极速初筛与排行榜：
   python -m cli batch --file alphas_sample.txt --export qualifying_alphas.csv

3. 因子库自相关性深度分析与拦截：
   python -m cli check-corr --expr "group_rank(ts_rank(sales / equity, 126), subindustry)"

4. 达标因子入库持久化：
   python -m cli commit --expr "..." --id "Alpha_Quality_01"

5. 离线数据集查看与构建：
   python -m cli dataset --info
"""

import sys
import json
import argparse
from pathlib import Path

# 编码与路径防御
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from data_loader.config import MASTER_PATH, COMMITTED_ALPHAS_PATH, OUTPUTS_DIR, LOGS_DIR, ensure_workspace_dirs
from data_loader.build_master_dataset import build_master_dataset
from engine.simulator import LocalWQSimulator, AlphaMetrics
from engine.correlation_checker import CorrelationChecker
from engine.visualizer import display_alpha_report, display_batch_leaderboard, console
from engine.wq_api import WorldQuantBrainClient, export_alphas_to_csv
from engine.logger import log_research_event, log_error


def get_simulator() -> LocalWQSimulator:
    """初始化并缓存仿真器与数据集"""
    if not MASTER_PATH.exists():
        console.print(f"[yellow]未检测到 {MASTER_PATH}，正在触发离线宽表自动构建...[/yellow]")
        build_master_dataset()

    df = pl.read_parquet(MASTER_PATH)
    corr_checker = CorrelationChecker()
    return LocalWQSimulator(df, corr_checker=corr_checker)


def cmd_run(args):
    """运行单因子极速回测"""
    sim = get_simulator()
    if not args.json:
        console.print(f"[bold cyan]正在启动极速仿真引擎编译并执行表达式...[/bold cyan]")

    metrics = sim.simulate(
        expression=args.expr,
        delay=args.delay,
        neutralization=args.neutralization,
        truncation=args.truncation,
        alpha_id=args.id,
        check_corr=not args.no_corr,
    )

    if args.json:
        result_payload = {
            "alpha_id": args.id or "LOCAL_ALPHA",
            "expression": args.expr,
            "runtime_ms": metrics.runtime_ms,
            "sharpe": metrics.sharpe,
            "fitness": metrics.fitness,
            "turnover": metrics.turnover,
            "returns": metrics.returns,
            "max_drawdown": metrics.max_drawdown,
            "margin_bps": metrics.margin,
            "sub_universe_sharpe": metrics.sub_universe_sharpe,
            "is_all_passed": metrics.is_all_passed(),
            "is_checks": metrics.is_checks,
        }
        print(json.dumps(result_payload, indent=2, ensure_ascii=False))
    else:
        display_alpha_report(
            expression=args.expr,
            metrics=metrics,
            alpha_id=args.id,
            delay=args.delay,
            neutralization=args.neutralization,
        )

    # 自动就地记录本次回测事件到当前工作目录 logs/
    log_research_event(
        event_type="run",
        expression=args.expr,
        metrics=metrics,
        alpha_id=args.id,
    )

    if args.commit:
        if metrics.daily_pnl.size > 0:
            alpha_id = args.id or f"Alpha_{args.expr[:20]}"
            sim.corr_checker.commit_alpha(
                alpha_id,
                metrics.daily_dates,
                metrics.daily_pnl,
                expression=args.expr,
                metrics=metrics,
            )
            if not args.json:
                console.print(f"[green]✔ 因子 '{alpha_id}' 已成功写入当前工作区因子库！[/green]")

    if args.submit:
        client = WorldQuantBrainClient()
        client.submit_alpha(args.expr, metrics, alpha_name=args.id)


def cmd_batch(args):
    """批量读取因子清单并执行极速初筛与排行榜生成"""
    file_path = Path(args.file)
    if not file_path.exists():
        console.print(f"[red]错误: 因子文件未找到: {file_path}[/red]")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not lines:
        console.print(f"[yellow]提示: {file_path} 中没有有效的因子表达式。[/yellow]")
        return

    if not args.json:
        console.print(f"[bold cyan]开始批量回测 {len(lines)} 个因子表达式...[/bold cyan]")
    sim = get_simulator()

    results = []
    qualifying_alphas = []

    for idx, expr in enumerate(lines, 1):
        alpha_id = f"Batch_Alpha_{idx:03d}"
        m = sim.simulate(
            expression=expr,
            delay=args.delay,
            neutralization=args.neutralization,
            truncation=args.truncation,
            alpha_id=alpha_id,
            check_corr=False,
        )
        record = {
            "id": alpha_id,
            "expression": expr,
            "metrics": m,
        }
        results.append(record)

        if m.sharpe >= args.min_sharpe and m.fitness >= args.min_fitness:
            qualifying_alphas.append(record)

    # 按 Fitness 降序排序
    results.sort(key=lambda x: x["metrics"].fitness, reverse=True)

    if args.json:
        batch_out = [
            {
                "id": r["id"],
                "expression": r["expression"],
                "sharpe": r["metrics"].sharpe,
                "fitness": r["metrics"].fitness,
                "turnover": r["metrics"].turnover,
                "returns": r["metrics"].returns,
                "max_drawdown": r["metrics"].max_drawdown,
                "sub_universe_sharpe": r["metrics"].sub_universe_sharpe,
                "is_all_passed": r["metrics"].is_all_passed(),
                "runtime_ms": r["metrics"].runtime_ms,
            }
            for r in results
        ]
        print(json.dumps(batch_out, indent=2, ensure_ascii=False))
    else:
        display_batch_leaderboard(results)
        console.print(f"\n[bold green]初筛完成！共 {len(results)} 个因子，其中 {len(qualifying_alphas)} 个达到预设门槛 (Sharpe >= {args.min_sharpe}, Fitness >= {args.min_fitness})。[/bold green]")

    if args.export:
        export_path = Path(args.export)
        if not export_path.is_absolute():
            ensure_workspace_dirs()
            export_path = OUTPUTS_DIR / export_path
        export_alphas_to_csv(results, export_path)
        if not args.json:
            console.print(f"[green]✔ 初筛达标结果已导出至当前工作区: {export_path}[/green]")

    # 批量事件记录流水账
    for r in results:
        log_research_event(
            event_type="batch",
            expression=r["expression"],
            metrics=r["metrics"],
            alpha_id=r["id"],
        )

    if args.submit and qualifying_alphas:
        if not args.json:
            console.print(f"[bold cyan]正在对 {len(qualifying_alphas)} 个达标因子执行批量提交...[/bold cyan]")
        client = WorldQuantBrainClient()
        for q in qualifying_alphas:
            client.submit_alpha(q["expression"], q["metrics"], alpha_name=q["id"])


def cmd_check_corr(args):
    """自相关性拦截与深度分析"""
    sim = get_simulator()
    console.print(f"[bold cyan]正在回测待测因子并扫描因子库相关性...[/bold cyan]")

    m = sim.simulate(args.expr, check_corr=False)
    if m.daily_pnl.size == 0:
        console.print("[red]错误: 因子有效日收益序列不足，无法进行相关性检测。[/red]")
        return

    passed, max_c, most_corr_id, all_corrs = sim.corr_checker.check_correlation(
        "Candidate_Alpha", m.daily_dates, m.daily_pnl, threshold=args.threshold
    )

    console.print(f"\n[bold white]待测表达式:[/bold white] [green]{args.expr}[/green]")
    console.print(f"[bold white]因子库对比数:[/bold white] {len(all_corrs)} 个历史已入库因子")
    color = 'green' if passed else 'red'
    console.print(f"[bold white]最高绝对相关系数:[/bold white] [{color}]{max_c:.4f}[/{color}] (对标因子: {most_corr_id})")
    status_str = "[bold green]PASS (低于 0.65 红线)[/bold green]" if passed else "[bold red]FAIL (触发自相关熔断拦截)[/bold red]"
    console.print(f"[bold white]判定结果:[/bold white] {status_str}")

    if all_corrs:
        from rich.table import Table
        from rich import box
        t = Table(title="与库内所有已提交因子的详细相关系数", box=box.ROUNDED)
        t.add_column("库内因子 ID", style="bold cyan")
        t.add_column("相关系数 (Pearson)", justify="center")
        t.add_column("红线风险", justify="center")
        for k, v in all_corrs.items():
            risk = "[red]HIGH RISK[/red]" if abs(v) >= 0.65 else "[green]SAFE[/green]"
            t.add_row(k, f"{v:+.4f}", risk)
        console.print(t)


def cmd_commit(args):
    """入库持久化"""
    sim = get_simulator()
    m = sim.simulate(args.expr, check_corr=False)
    alpha_id = args.id or f"Alpha_{args.expr[:20]}"
    sim.corr_checker.commit_alpha(alpha_id, m.daily_dates, m.daily_pnl, expression=args.expr, metrics=m)
    log_research_event("commit", args.expr, m, alpha_id=alpha_id)
    console.print(f"[green]✔ 因子 '{alpha_id}' 已成功写入当前工作区因子库: {COMMITTED_ALPHAS_PATH}[/green]")


FIELD_CATALOG = [
    {
        "category": "行情量价 (Price-Volume)",
        "fields": [
            ("close", "当日收盘价", "基准价格信号，close / ts_delay(close, 1)"),
            ("open", "当日开盘价", "日内跳空与价差 (close - open) / open"),
            ("high", "当日最高价", "波动振幅 (high - low) / close"),
            ("low", "当日最低价", "低点支撑与反转信号"),
            ("volume", "当日成交量", "成交量量能指标"),
            ("vwap", "成交量加权平均价", "微观结构基准价格，(vwap - close) / close"),
            ("returns", "当日收益率", "close / ts_delay(close, 1) - 1"),
            ("cap", "总市值", "单位: USD，cap > 1e9"),
            ("adv20", "20日日均成交额", "流动性加权与过滤"),
            ("shares_outstanding", "发行在外普通股股数", "别名: shares, sharesout"),
        ]
    },
    {
        "category": "资产负债表 - 资产类 (Assets)",
        "fields": [
            ("assets", "总资产 (Assets)", "别名: total_assets，ROA分母"),
            ("assets_curr", "流动资产 (Current Assets)", "别名: current_assets，短期偿债能力"),
            ("cash", "货币资金与等价物", "别名: cash_and_equivalents，安全边际"),
            ("cash_st", "现金与短期投资", "别名: cash_and_short_term_investments"),
            ("receivable", "应收账款净额", "别名: accounts_receivable，盈余质量与回款周期"),
            ("inventory", "存货净额", "别名: inventories，存货周转率分母"),
            ("ppent", "固定资产净额 (PPE Net)", "别名: fixed_assets, ppe，重资产重估"),
            ("goodwill", "商誉净额", "别名: total_goodwill，并购溢价与减值风险"),
            ("intangible_assets", "无形资产", "别名: finite_intangibles"),
        ]
    },
    {
        "category": "资产负债表 - 负债与权益 (Liabilities & Equity)",
        "fields": [
            ("liabilities", "总负债 (Total Liabilities)", "杠杆率分母，liabilities / assets"),
            ("liabilities_curr", "流动负债 (Current Liabilities)", "短期偿债压力"),
            ("total_debt", "总有息负债", "别名: debt，财务杠杆风险"),
            ("debt_st", "短期有息债务", "别名: short_term_debt，到期偿付压力"),
            ("accounts_payable", "应付账款", "别名: ap，商业信用与上下游议价力"),
            ("equity", "股东权益 / 净资产", "别名: stockholders_equity, bookvalue，ROE分母"),
            ("retained_earnings", "留存收益", "公司历史盈余积累"),
        ]
    },
    {
        "category": "利润表 (Income Statement)",
        "fields": [
            ("sales", "营业总收入", "别名: revenues, revenue, turnover，成长性核心"),
            ("cogs", "营业成本 (COGS)", "别名: cost_of_goods_sold，生产直接成本"),
            ("gross_profit", "毛利润 (Gross Profit)", "sales - cogs，毛利率分母"),
            ("operating_income", "营业利润 (EBIT)", "别名: ebit, op_income，主营盈利能力"),
            ("net_income", "净利润 (Net Income)", "别名: income, ni, net_earnings，底线利润"),
            ("interest_expense", "利息支出", "偿债负担与利息覆盖倍数"),
            ("rd_expense", "研发费用 (R&D)", "别名: rnd_expense，科技创新投入"),
            ("sga_expense", "销售及行政开支 (SG&A)", "运营管理效率"),
            ("income_tax", "所得税费用", "税负比率分析"),
        ]
    },
    {
        "category": "现金流量表 (Cash Flow)",
        "fields": [
            ("cashflow_op", "经营现金流净额 (CFO)", "别名: operating_cashflow, cfo，真实现金造血"),
            ("capex", "资本性支出 (CapEx)", "固定资产投资与扩产支出"),
            ("fcf", "自由现金流 (FCF)", "cashflow_op - capex，真实回报"),
            ("cashflow_invst", "投资活动现金流净额", "对外投资与购建长期资产"),
            ("cashflow_fin", "筹资活动现金流净额", "股权/债务融资与派息还债"),
            ("cashflow_dividends", "派发现金红利", "别名: dividends，分红收益率"),
            ("depreciation", "折旧与摊销 (D&A)", "别名: depr，非现金成本调整"),
            ("value_of_shares_reacquired_during_period", "股票回购金额", "股份回购注销，股东回报"),
        ]
    },
    {
        "category": "财务比率与估值 (Ratios & Valuation)",
        "fields": [
            ("working_capital", "净营运资本 (NWC)", "assets_curr - liabilities_curr"),
            ("current_ratio", "流动比率", "assets_curr / liabilities_curr"),
            ("inventory_turnover", "存货周转率", "cogs / inventory"),
            ("ebitda", "税息折旧摊销前利润", "operating_income + depreciation"),
            ("roic", "投入资本回报率", "operating_income / (equity + total_debt)"),
            ("asset_turnover", "总资产周转率", "sales / assets"),
            ("ev", "企业价值 (EV)", "cap + total_debt - cash"),
            ("est_eps", "分析师预期EPS", "一致预期盈利信号"),
        ]
    },
    {
        "category": "风险模型与波动率 (Risk & Volatility)",
        "fields": [
            ("beta_last_30_days_spy", "大盘滚动Beta(30日)", "别名: beta，相对标普500系统性敏感度"),
            ("volatility_20", "20日年化波动率", "短周期波动率反转/规避"),
            ("volatility_60", "60日年化波动率", "中周期波动率基准"),
        ]
    },
    {
        "category": "截面与分组标识 (Metadata & Grouping)",
        "fields": [
            ("ticker", "股票代码", "标的唯一代码 (如 AAPL, MSFT)"),
            ("date", "交易日期", "时间序列主键 (YYYY-MM-DD)"),
            ("filed_date", "SEC 财报最新披露日", "点对点无未来函数时间戳"),
            ("subindustry", "GICS 细分行业", "组内中性化核心分组列 (subindustry)"),
            ("is_top1000", "Top 1000 市值标记", "Sub-universe 过滤标记"),
        ]
    },
]


def cmd_fields(args):
    """查看或搜索支持的所有字段与同义词"""
    from rich.table import Table
    from rich import box

    search = (args.search or "").strip().lower()
    cat_filter = (args.category or "").strip().lower()

    if args.json:
        results = []
        for cat in FIELD_CATALOG:
            for fname, desc, usage in cat["fields"]:
                if search and search not in fname.lower() and search not in desc.lower() and search not in usage.lower():
                    continue
                if cat_filter and cat_filter not in cat["category"].lower():
                    continue
                results.append({
                    "category": cat["category"],
                    "field": fname,
                    "description": desc,
                    "details": usage,
                })
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    table = Table(
        title="✨ WorldQuant BRAIN 本地引擎已支持字段词典 (59 核心宽表列 + 自动同义词) ✨",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("类别", style="bold magenta", width=24)
    table.add_column("字段名称 (Field)", style="bold green", width=22)
    table.add_column("中文释义", style="white", width=26)
    table.add_column("别名 / 用途说明", style="yellow", width=42)

    total_shown = 0
    for cat in FIELD_CATALOG:
        for fname, desc, usage in cat["fields"]:
            if search and (search not in fname.lower() and search not in desc.lower() and search not in usage.lower()):
                continue
            if cat_filter and cat_filter not in cat["category"].lower():
                continue
            table.add_row(cat["category"], fname, desc, usage)
            total_shown += 1

    console.print(table)
    console.print(f"[bold white]共显示 [green]{total_shown}[/green] 个字段。[/bold white]")
    console.print(
        "[dim]提示: 可使用 [bold cyan]python -m cli fields --search <关键词>[/bold cyan] 过滤；\n"
        "Web GUI (python gui.py) 右上角点击 [bold cyan]📖 字段与算子词典[/bold cyan] 可直接点击标签插入公式！[/dim]\n"
    )


def cmd_dataset(args):
    """数据集管理与查看"""
    if args.build:
        build_master_dataset()
    elif args.fields:
        cmd_fields(args)
    elif args.info:
        if not MASTER_PATH.exists():
            console.print(f"[red]未找到数据集: {MASTER_PATH}[/red]")
            return
        df = pl.read_parquet(MASTER_PATH)
        console.print(f"[bold cyan]=== 本地离线 Master Dataset 概况 ===[/bold cyan]")
        console.print(f"文件位置: {MASTER_PATH}")
        console.print(f"数据量: [bold green]{df.shape[0]:,}[/bold green] 行 x [bold green]{df.shape[1]}[/bold green] 列")
        console.print(f"股票数: {df['ticker'].n_unique()} 只")
        console.print(f"时间跨度: {df['date'].min()} ~ {df['date'].max()}")
        console.print(f"可用字段: {', '.join(df.columns)}")


def cmd_gui(args):
    """启动本地图形化回测界面"""
    from gui import start_gui
    start_gui(host=args.host, port=args.port, open_browser=not args.no_browser)


def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN 本地极速量化回测与初筛引擎")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 1. run 命令
    run_parser = subparsers.add_parser("run", help="执行单因子回测")
    run_parser.add_argument("--expr", type=str, required=True, help="WorldQuant FastExpr 表达式")
    run_parser.add_argument("--id", type=str, default=None, help="因子唯一标识 ID")
    run_parser.add_argument("--delay", type=int, default=1, help="交易延迟天数 (默认: 1)")
    run_parser.add_argument("--neutralization", type=str, default="SUBINDUSTRY", help="中性化方式 (默认: SUBINDUSTRY)")
    run_parser.add_argument("--truncation", type=float, default=0.08, help="极值截断阈值 (默认: 0.08)")
    run_parser.add_argument("--no-corr", action="store_true", help="跳过自相关性检测")
    run_parser.add_argument("--commit", action="store_true", help="回测后自动加入已提交因子库")
    run_parser.add_argument("--submit", action="store_true", help="一键提交至 WorldQuant BRAIN")
    run_parser.add_argument("--json", action="store_true", help="以标准 JSON 格式输出结果 (供 Agent/流水线解析)")

    # 2. batch 命令
    batch_parser = subparsers.add_parser("batch", help="批量因子初筛")
    batch_parser.add_argument("--file", type=str, required=True, help="因子清单文件路径")
    batch_parser.add_argument("--min-sharpe", type=float, default=1.25, help="初筛最低 Sharpe (默认: 1.25)")
    batch_parser.add_argument("--min-fitness", type=float, default=1.0, help="初筛最低 Fitness (默认: 1.0)")
    batch_parser.add_argument("--delay", type=int, default=1, help="交易延迟天数")
    batch_parser.add_argument("--neutralization", type=str, default="SUBINDUSTRY", help="中性化方式")
    batch_parser.add_argument("--truncation", type=float, default=0.08, help="极值截断阈值")
    batch_parser.add_argument("--export", type=str, default=None, help="结果导出 CSV 路径")
    batch_parser.add_argument("--submit", action="store_true", help="自动提交所有达标因子")
    batch_parser.add_argument("--json", action="store_true", help="以标准 JSON 格式输出结果 (供 Agent/流水线解析)")

    # 3. check-corr 命令
    corr_parser = subparsers.add_parser("check-corr", help="因子库自相关性检测")
    corr_parser.add_argument("--expr", type=str, required=True, help="待测表达式")
    corr_parser.add_argument("--threshold", type=float, default=0.65, help="相关性预警阈值 (默认: 0.65)")

    # 4. commit 命令
    commit_parser = subparsers.add_parser("commit", help="将因子收益序列持久化入库")
    commit_parser.add_argument("--expr", type=str, required=True, help="表达式")
    commit_parser.add_argument("--id", type=str, required=True, help="因子名称/ID")

    # 5. dataset 命令
    ds_parser = subparsers.add_parser("dataset", help="管理离线数据集")
    ds_parser.add_argument("--info", action="store_true", help="查看数据集概况")
    ds_parser.add_argument("--build", action="store_true", help="重新构建全量数据集")
    ds_parser.add_argument("--fields", action="store_true", help="查看支持的字段列表与同义词")
    ds_parser.add_argument("--search", type=str, default=None, help="搜索字段关键词")
    ds_parser.add_argument("--category", type=str, default=None, help="按类别过滤字段")
    ds_parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # 6. fields 命令 (直达字段词典)
    fields_parser = subparsers.add_parser("fields", help="查询已支持的所有字段、同义词与量化用途")
    fields_parser.add_argument("--search", type=str, default=None, help="搜索字段关键词 (例如 income, debt, return)")
    fields_parser.add_argument("--category", type=str, default=None, help="按类别过滤 (如 price, assets, income, cashflow)")
    fields_parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # 7. gui 命令
    gui_parser = subparsers.add_parser("gui", help="启动本地图形化回测界面 (Web GUI)")
    gui_parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定主机地址 (默认: 127.0.0.1)")
    gui_parser.add_argument("--port", type=int, default=8888, help="服务端口号 (默认: 8888)")
    gui_parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")

    args = parser.parse_args()
    if not args.command:
        # Default to interactive wizard when no command-line flags are given
        from run import interactive_main
        interactive_main()
        return

    if args.command == "run":
        cmd_run(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "check-corr":
        cmd_check_corr(args)
    elif args.command == "commit":
        cmd_commit(args)
    elif args.command == "dataset":
        cmd_dataset(args)
    elif args.command == "fields":
        cmd_fields(args)
    elif args.command == "gui":
        cmd_gui(args)


if __name__ == "__main__":
    main()
