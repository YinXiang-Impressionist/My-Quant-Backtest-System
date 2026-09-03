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
from data_loader.config import MASTER_PATH, COMMITTED_ALPHAS_PATH
from data_loader.build_master_dataset import build_master_dataset
from engine.simulator import LocalWQSimulator, AlphaMetrics
from engine.correlation_checker import CorrelationChecker
from engine.visualizer import display_alpha_report, display_batch_leaderboard, console
from engine.wq_api import WorldQuantBrainClient, export_alphas_to_csv


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

    if args.commit:
        if metrics.daily_pnl.size > 0:
            sim.corr_checker.commit_alpha(
                args.id or f"Alpha_{args.expr[:20]}",
                metrics.daily_dates,
                metrics.daily_pnl,
            )
            if not args.json:
                console.print("[green]✔ 因子已成功入库到本地已提交因子库！[/green]")

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
        export_alphas_to_csv(results, export_path)

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
    sim.corr_checker.commit_alpha(alpha_id, m.daily_dates, m.daily_pnl)
    console.print(f"[green]✔ 因子 '{alpha_id}' 已成功写入本地因子库: {COMMITTED_ALPHAS_PATH}[/green]")


def cmd_dataset(args):
    """数据集管理与查看"""
    if args.build:
        build_master_dataset()
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

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
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


if __name__ == "__main__":
    main()
