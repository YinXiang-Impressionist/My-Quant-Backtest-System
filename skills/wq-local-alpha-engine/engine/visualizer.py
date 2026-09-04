"""
WorldQuant BRAIN 本地回测终端富文本仪表盘 (Rich Visualizer)
跨平台与 Windows GBK 编码安全设计
"""

import sys
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .simulator import AlphaMetrics

# Windows UTF-8 编码防御
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(force_terminal=True, legacy_windows=False)


def display_alpha_report(
    expression: str,
    metrics: AlphaMetrics,
    alpha_id: Optional[str] = None,
    delay: int = 1,
    universe: str = "USA TOP3000",
    neutralization: str = "SUBINDUSTRY"
):
    """打印单因子高保真回测富文本报告看板"""
    title_text = Text("[WorldQuant BRAIN Local Engine - Alpha Report]", style="bold cyan")

    # 顶部元数据
    meta_info = (
        f"[bold white]Expression:[/bold white] [green]{expression}[/green]\n"
        f"[bold white]Alpha ID:[/bold white] {alpha_id or 'LOCAL_ALPHA'} | "
        f"[bold white]Universe:[/bold white] {universe} | "
        f"[bold white]Delay:[/bold white] {delay} | "
        f"[bold white]Neutralization:[/bold white] {neutralization} | "
        f"[bold white]Engine Speed:[/bold white] [bold yellow]{metrics.runtime_ms:.2f} ms[/bold yellow] (Ultra-Fast)"
    )
    console.print(Panel(meta_info, title=title_text, border_style="cyan", box=box.ROUNDED))

    # 核心指标表格
    metrics_table = Table(title="Performance Metrics (WorldQuant Official)", box=box.SIMPLE_HEAVY)
    metrics_table.add_column("Sharpe", justify="center", style="bold magenta")
    metrics_table.add_column("Fitness", justify="center", style="bold cyan")
    metrics_table.add_column("Turnover", justify="center", style="bold yellow")
    metrics_table.add_column("Returns", justify="center", style="bold green")
    metrics_table.add_column("Max Drawdown", justify="center", style="bold red")
    metrics_table.add_column("Margin (bps)", justify="center", style="white")
    metrics_table.add_column("Sub-Universe (TOP1000)", justify="center", style="blue")

    metrics_table.add_row(
        f"{metrics.sharpe:.3f}",
        f"{metrics.fitness:.3f}",
        f"{metrics.turnover * 100:.2f}%",
        f"{metrics.returns * 100:.2f}%",
        f"{metrics.max_drawdown * 100:.2f}%",
        f"{metrics.margin:.2f}",
        f"{metrics.sub_universe_sharpe:.3f}",
    )
    console.print(metrics_table)

    # IS 质检红线表格
    is_table = Table(title="WorldQuant In-Sample (IS) Quality Matrix", box=box.ROUNDED)
    is_table.add_column("Check Item", style="bold white")
    is_table.add_column("Status", justify="center")
    is_table.add_column("Rule & Detail", style="dim")

    check_descriptions = {
        "LOW_SHARPE": "Sharpe >= 1.25",
        "LOW_FITNESS": "Fitness >= 1.0",
        "TURNOVER": "1.0% <= Turnover <= 70.0%",
        "DRAWDOWN": "Max Drawdown < 25.0%",
        "SUB_UNIVERSE_TOP1000": "Sub-Universe Sharpe >= 1.0",
        "SELF_CORRELATION": "Max Pearson Corr < 0.65",
    }

    all_passed = True
    for check_name, check_val in metrics.is_checks.items():
        if check_val == "PASS" or check_val.startswith("PASS"):
            status_text = Text("[PASS]", style="bold green")
        elif "WARN" in check_val:
            status_text = Text(f"[WARN] {check_val}", style="bold yellow")
        else:
            status_text = Text(f"[FAIL] {check_val}", style="bold red")
            all_passed = False

        desc = check_descriptions.get(check_name, "")
        is_table.add_row(check_name, status_text, desc)

    console.print(is_table)

    # 结果判定横幅
    if all_passed:
        console.print(Panel("[bold green]CONGRATULATIONS: ALPHA PASSED ALL WORLDQUANT IS CHECKS![/bold green]", box=box.HEAVY))
    else:
        console.print(Panel("[bold yellow]NOTICE: Some IS criteria not met. Please optimize further.[/bold yellow]", box=box.HEAVY))


def display_batch_leaderboard(results: List[dict]):
    """展示批量初筛排行榜"""
    table = Table(title="WorldQuant BRAIN Batch Screening Leaderboard (Sorted by Fitness)", box=box.ROUNDED)
    table.add_column("Rank", justify="center", style="bold cyan")
    table.add_column("Alpha ID / Expression", style="white", max_width=45, overflow="fold")
    table.add_column("Sharpe", justify="center", style="magenta")
    table.add_column("Fitness", justify="center", style="bold cyan")
    table.add_column("Turnover", justify="center", style="yellow")
    table.add_column("Sub Sharpe", justify="center", style="blue")
    table.add_column("Speed", justify="center", style="dim")
    table.add_column("IS Status", justify="center")

    for idx, r in enumerate(results, 1):
        m: AlphaMetrics = r["metrics"]
        expr = r["expression"]
        alpha_id = r.get("id", f"Alpha_{idx:03d}")

        is_pass = m.is_all_passed()
        status = "[bold green]PASS[/bold green]" if is_pass else "[red]FAIL[/red]"

        table.add_row(
            str(idx),
            f"[bold]{alpha_id}[/bold]\n[dim]{expr}[/dim]",
            f"{m.sharpe:.2f}",
            f"{m.fitness:.2f}",
            f"{m.turnover * 100:.1f}%",
            f"{m.sub_universe_sharpe:.2f}",
            f"{m.runtime_ms:.1f}ms",
            status
        )

    console.print(table)
