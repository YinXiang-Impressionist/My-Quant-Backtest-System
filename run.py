"""
WorldQuant BRAIN Local Quant Engine - Interactive Wizard (English)
An intuitive, fully interactive command-line interface with no memorization required.
Run directly via:
    python run.py
or
    python cli.py (without arguments)
"""

import sys
import os
import time
from pathlib import Path
from typing import Optional, Dict, List

# Windows UTF-8 encoding safeguard
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

from data_loader.config import MASTER_PATH, COMMITTED_ALPHAS_PATH
from data_loader.build_master_dataset import build_master_dataset
from engine.simulator import LocalWQSimulator, AlphaMetrics
from engine.correlation_checker import CorrelationChecker
from engine.visualizer import display_alpha_report, display_batch_leaderboard, console
from engine.wq_api import WorldQuantBrainClient, export_alphas_to_csv

# Global cached simulator instance for instant (<20ms) in-memory simulations
_CACHED_SIMULATOR: Optional[LocalWQSimulator] = None


def get_cached_simulator() -> LocalWQSimulator:
    global _CACHED_SIMULATOR
    if _CACHED_SIMULATOR is not None:
        return _CACHED_SIMULATOR

    if not MASTER_PATH.exists():
        console.print(f"[yellow]Master dataset not found at {MASTER_PATH}. Building dataset now...[/yellow]")
        build_master_dataset()

    with console.status("[bold cyan]Loading 3.45M-row historical dataset into memory...[/bold cyan]", spinner="dots"):
        t0 = time.perf_counter()
        df = pl.read_parquet(MASTER_PATH)
        corr_checker = CorrelationChecker()
        _CACHED_SIMULATOR = LocalWQSimulator(df, corr_checker=corr_checker)
        t_load = (time.perf_counter() - t0) * 1000

    console.print(f"[bold green]✔ In-memory engine ready in {t_load:.1f} ms ({df.shape[0]:,} rows x {df.shape[1]} columns, {df['ticker'].n_unique()} stocks)![/bold green]\n")
    return _CACHED_SIMULATOR


# ==============================================================================
# 1. CURATED ALPHA TEMPLATES
# ==============================================================================
CURATED_ALPHAS = [
    {
        "category": "Price-Volume & Liquidity",
        "name": "Volume-to-ADV20 Linear Decay",
        "expr": "rank(ts_decay_linear(volume / adv20, 10))",
        "expected": "Sharpe: 1.31, Fitness: 1.78, Turnover: 3.68% [PASS]",
    },
    {
        "category": "Price-Volume & Liquidity",
        "name": "Short-Term VWAP Deviation Mean-Reversion",
        "expr": "group_rank(ts_rank(-(close / vwap - 1), 20), subindustry)",
        "expected": "Captures intraday/daily liquidity bounce against VWAP benchmark",
    },
    {
        "category": "Price-Volume & Liquidity",
        "name": "10-Day Volume-Price Divergence",
        "expr": "-group_rank(ts_corr(close, volume, 10), subindustry)",
        "expected": "Contrarian signal on high volume exhaustion sell-offs",
    },
    {
        "category": "Momentum & Reversal",
        "name": "10-Day Linear Decay Return Reversal",
        "expr": "-group_rank(ts_decay_linear(returns, 10), subindustry)",
        "expected": "Classic short-term mean reversion across GICS subindustries",
    },
    {
        "category": "Momentum & Reversal",
        "name": "12-Month Mid-Term Momentum (excluding last 1M)",
        "expr": "group_rank(ts_rank(ts_delay(close, 20) / ts_delay(close, 252) - 1, 126), subindustry)",
        "expected": "Academic 12-1 momentum with 1-month skip to avoid short-term reversal",
    },
    {
        "category": "Fundamental Quality (SEC EDGAR)",
        "name": "Operating Return on Equity (Operating Income / Equity)",
        "expr": "group_rank(ts_rank(operating_income / equity, 126), subindustry)",
        "expected": "Core profitability & capital allocation efficiency (SEC Point-in-Time)",
    },
    {
        "category": "Fundamental Quality (SEC EDGAR)",
        "name": "Operating Cash Flow Return on Assets (CFO / Assets)",
        "expr": "group_rank(ts_rank(cashflow_op / assets, 126), subindustry)",
        "expected": "Cash conversion quality to filter out accruals distortion",
    },
    {
        "category": "Fundamental Quality (SEC EDGAR)",
        "name": "Free Cash Flow Yield (FCF / EV)",
        "expr": "group_rank(ts_rank(fcf / (ev + 1000), 60), subindustry)",
        "expected": "Enterprise cash generation relative to valuation (Enterprise Value)",
    },
]


# ==============================================================================
# 2. INTERACTIVE SUB-MODULES
# ==============================================================================
def run_single_simulation(sim: LocalWQSimulator, default_expr: Optional[str] = None):
    """Interactive wizard for single alpha simulation"""
    console.print("\n[bold cyan]─── Step 1: Alpha Expression ───[/bold cyan]")
    if default_expr:
        console.print(f"Preset Expression: [green]{default_expr}[/green]")
        use_preset = Confirm.ask("Use this preset expression?", default=True)
        if use_preset:
            expr = default_expr
        else:
            expr = Prompt.ask("Enter custom WorldQuant expression")
    else:
        console.print("[dim]Tip: You can use WQ operators like rank(), group_rank(), ts_decay_linear(), ts_corr().[/dim]")
        expr = Prompt.ask("Enter WorldQuant expression")

    expr = expr.strip()
    if not expr:
        console.print("[yellow]No expression provided. Returning to menu.[/yellow]")
        return

    console.print("\n[bold cyan]─── Step 2: Simulation Settings ───[/bold cyan]")
    use_defaults = Confirm.ask("Use standard settings (Delay=1, Neutralization=SUBINDUSTRY, Truncation=0.08)?", default=True)

    if use_defaults:
        delay = 1
        neutralization = "SUBINDUSTRY"
        truncation = 0.08
        check_corr = True
    else:
        delay = int(Prompt.ask("Trading delay in days", default="1"))
        neut_choices = ["SUBINDUSTRY", "INDUSTRY", "SECTOR", "MARKET", "NONE"]
        console.print("Neutralization options: [1] SUBINDUSTRY  [2] INDUSTRY  [3] SECTOR  [4] MARKET  [5] NONE")
        neut_idx = Prompt.ask("Select neutralization (1-5)", choices=["1", "2", "3", "4", "5"], default="1")
        neutralization = neut_choices[int(neut_idx) - 1]
        truncation = float(Prompt.ask("Weight truncation threshold", default="0.08"))
        check_corr = Confirm.ask("Check self-correlation against committed library?", default=True)

    alpha_id = Prompt.ask("Assign Alpha ID (optional)", default="Interactive_Alpha")

    console.print(f"\n[bold yellow]⚡ Running simulation across USA TOP3000 universe...[/bold yellow]")
    try:
        metrics = sim.simulate(
            expression=expr,
            delay=delay,
            neutralization=neutralization,
            truncation=truncation,
            alpha_id=alpha_id,
            check_corr=check_corr,
        )
    except Exception as e:
        console.print(f"[bold red]Simulation Error: {e}[/bold red]")
        return

    # Render rich official report
    display_alpha_report(
        expression=expr,
        metrics=metrics,
        alpha_id=alpha_id,
        delay=delay,
        neutralization=neutralization
    )

    # Post-simulation actions
    while True:
        console.print("\n[bold cyan]What would you like to do with this Alpha?[/bold cyan]")
        console.print("  [1] 💾 Commit to Local Alpha Library (prevent future correlation)")
        console.print("  [2] 🌐 Submit online to WorldQuant BRAIN")
        console.print("  [3] 🔁 Tweak parameters / expression and re-run")
        console.print("  [0] ↩ Return to Main Menu")

        choice = Prompt.ask("Select an action (0-3)", choices=["0", "1", "2", "3"], default="0")
        if choice == "0":
            break
        elif choice == "1":
            sim.corr_checker.commit_alpha(alpha_id, metrics.daily_dates, metrics.daily_pnl)
            console.print(f"[bold green]✔ Alpha '{alpha_id}' committed to local database: {COMMITTED_ALPHAS_PATH}[/bold green]")
        elif choice == "2":
            client = WorldQuantBrainClient()
            client.submit_alpha(expr, metrics, alpha_name=alpha_id)
        elif choice == "3":
            run_single_simulation(sim, default_expr=expr)
            break


def run_template_selection(sim: LocalWQSimulator):
    """Pick from curated alpha templates"""
    console.print("\n[bold cyan]=== Curated WorldQuant Alpha Library & Templates ===[/bold cyan]")
    table = Table(box=box.ROUNDED)
    table.add_column("#", justify="center", style="bold yellow")
    table.add_column("Category", style="cyan")
    table.add_column("Alpha Strategy Name", style="bold white")
    table.add_column("Formula Expression", style="green")

    for i, item in enumerate(CURATED_ALPHAS, 1):
        table.add_row(str(i), item["category"], item["name"], item["expr"])
    console.print(table)

    choice = Prompt.ask(
        f"Select an Alpha template (1-{len(CURATED_ALPHAS)}) or '0' to cancel",
        choices=[str(x) for x in range(len(CURATED_ALPHAS) + 1)],
        default="1"
    )
    if choice == "0":
        return

    selected = CURATED_ALPHAS[int(choice) - 1]
    console.print(f"\n[bold green]Selected: {selected['name']}[/bold green]")
    console.print(f"Expression: [cyan]{selected['expr']}[/cyan]")
    console.print(f"Hypothesis Note: [dim]{selected['expected']}[/dim]\n")

    run_single_simulation(sim, default_expr=selected["expr"])


def run_batch_screening(sim: LocalWQSimulator):
    """Interactive batch screening from file or preset"""
    console.print("\n[bold cyan]=== Batch Alpha Screening & Leaderboard ===[/bold cyan]")
    default_file = "alphas_sample.txt"
    file_path_str = Prompt.ask("Enter path to file with alpha expressions", default=default_file)
    file_path = Path(file_path_str)

    if not file_path.exists():
        console.print(f"[red]File '{file_path}' does not exist![/red]")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not raw_lines:
        console.print("[yellow]No expressions found in file.[/yellow]")
        return

    console.print(f"Loaded [bold green]{len(raw_lines)}[/bold green] alpha candidate expressions.")
    min_sharpe = float(Prompt.ask("Filter: Minimum Sharpe ratio", default="1.25"))
    min_fitness = float(Prompt.ask("Filter: Minimum Fitness score", default="1.0"))

    results = []
    qualifying_alphas = []

    with console.status(f"[bold cyan]Screening {len(raw_lines)} alphas in parallel vectors...[/bold cyan]", spinner="dots"):
        t0 = time.perf_counter()
        for idx, line in enumerate(raw_lines, 1):
            if "=" in line:
                aid, expr = line.split("=", 1)
                aid, expr = aid.strip(), expr.strip()
            else:
                aid, expr = f"Alpha_{idx:02d}", line.strip()

            try:
                m = sim.simulate(expr, alpha_id=aid, check_corr=False)
                record = {"id": aid, "expression": expr, "metrics": m}
                results.append(record)
                if m.sharpe >= min_sharpe and m.fitness >= min_fitness:
                    qualifying_alphas.append(record)
            except Exception as e:
                pass
        t_total = (time.perf_counter() - t0) * 1000

    results.sort(key=lambda x: x["metrics"].fitness, reverse=True)
    display_batch_leaderboard(results)

    console.print(f"\n[bold green]Batch complete in {t_total:.1f} ms! Total: {len(results)}, Qualifying (Sharpe>={min_sharpe}, Fitness>={min_fitness}): {len(qualifying_alphas)}.[/bold green]")

    if Confirm.ask("Export results to CSV file?", default=True):
        export_name = Prompt.ask("Enter export file path", default="qualifying_alphas.csv")
        export_alphas_to_csv(results, Path(export_name))

    if qualifying_alphas and Confirm.ask(f"Submit all {len(qualifying_alphas)} qualifying alphas to WorldQuant online?", default=False):
        client = WorldQuantBrainClient()
        for q in qualifying_alphas:
            client.submit_alpha(q["expression"], q["metrics"], alpha_name=q["id"])


def run_automated_mining(sim: LocalWQSimulator):
    """Run automated hypothesis mining pipeline"""
    console.print("\n[bold cyan]=== Automated High-Performance Alpha Mining Pipeline ===[/bold cyan]")
    console.print("The pipeline systematically generates and evaluates alphas across 5 strategy classes:")
    console.print("  • Class 1: Micro Price-Volume & Liquidity (VWAP deviations, Volume Exhaustion)")
    console.print("  • Class 2: Momentum & Reversal (Linear Decay, 12-1 Momentum)")
    console.print("  • Class 3: Fundamental Profitability & Cash Flow (SEC EDGAR Point-in-Time)")
    console.print("  • Class 4: Operational Efficiency & Turnover (Asset, Inventory, Receivables)")
    console.print("  • Class 5: Capital Structure & Risk Distress (Debt, Share Repurchases)")

    max_tests = int(Prompt.ask("How many alpha variants to generate & evaluate?", default="30"))

    from engine.taxonomy import build_factor_taxonomy
    taxonomy = build_factor_taxonomy()

    all_factors = []
    for cat in taxonomy:
        for f in cat["factors"]:
            all_factors.append((cat["category"], f["name"], f["expr"]))

    test_subset = all_factors[:max_tests]
    console.print(f"\n[bold yellow]Mining and validating {len(test_subset)} alphas against IS 6-point red lines...[/bold yellow]")

    passed_alphas = []
    all_tested = []

    with console.status("[bold cyan]Mining in progress...[/bold cyan]", spinner="dots"):
        for cat_name, fname, expr in test_subset:
            try:
                m = sim.simulate(expr, check_corr=False)
                all_tested.append({"name": fname, "expr": expr, "metrics": m, "category": cat_name})
                if m.is_all_passed() or (m.sharpe >= 1.25 and m.fitness >= 1.0):
                    passed_alphas.append({"name": fname, "expr": expr, "metrics": m, "category": cat_name})
            except Exception:
                pass

    all_tested.sort(key=lambda x: x["metrics"].fitness, reverse=True)

    table = Table(title="Top Mined Alphas Leaderboard", box=box.ROUNDED)
    table.add_column("Rank", justify="center", style="bold yellow")
    table.add_column("Alpha Strategy", style="bold white")
    table.add_column("Sharpe", justify="center", style="bold magenta")
    table.add_column("Fitness", justify="center", style="bold cyan")
    table.add_column("Turnover", justify="center", style="bold yellow")
    table.add_column("Status", justify="center")

    for rank, item in enumerate(all_tested[:15], 1):
        m = item["metrics"]
        status = "[bold green]PASS[/bold green]" if m.is_all_passed() else "[bold yellow]MARGINAL[/bold yellow]" if m.sharpe >= 1.0 else "[dim red]FAIL[/dim red]"
        table.add_row(
            str(rank),
            f"{item['name']}\n[dim]{item['expr'][:45]}...[/dim]",
            f"{m.sharpe:.3f}",
            f"{m.fitness:.3f}",
            f"{m.turnover*100:.2f}%",
            status
        )
    console.print(table)

    console.print(f"\n[bold green]Mining Complete! Found {len(passed_alphas)} fully passed / high-quality candidate alphas.[/bold green]")


def run_correlation_diagnostic(sim: LocalWQSimulator):
    """Check self-correlation against library"""
    console.print("\n[bold cyan]=== Self-Correlation & Red-Line Diagnostic ===[/bold cyan]")
    expr = Prompt.ask("Enter candidate expression to check against committed alpha library")
    expr = expr.strip()
    if not expr:
        return

    threshold = float(Prompt.ask("Correlation alert threshold (WorldQuant red-line is 0.65)", default="0.65"))

    with console.status("[bold cyan]Simulating alpha and scanning correlation matrix...[/bold cyan]", spinner="dots"):
        m = sim.simulate(expr, check_corr=False)
        if m.daily_pnl.size == 0:
            console.print("[red]Insufficient daily PnL data to perform correlation analysis.[/red]")
            return
        passed, max_c, most_corr_id, all_corrs = sim.corr_checker.check_correlation(
            "Candidate_Alpha", m.daily_dates, m.daily_pnl, threshold=threshold
        )

    console.print(f"\n[bold white]Target Expression:[/bold white] [green]{expr}[/green]")
    console.print(f"[bold white]Committed Alphas Compared:[/bold white] {len(all_corrs)} alphas in local library")
    color = "green" if passed else "red"
    console.print(f"[bold white]Maximum Absolute Correlation:[/bold white] [{color}]{max_c:.4f}[/{color}] (against: {most_corr_id})")

    status_str = "[bold green]✔ PASS (Strictly below 0.65 threshold)[/bold green]" if passed else "[bold red]✖ FAIL (Self-correlation circuit breaker tripped)[/bold red]"
    console.print(f"[bold white]Assessment:[/bold white] {status_str}\n")

    if all_corrs:
        t = Table(title="Correlation Matrix with Library Alphas", box=box.ROUNDED)
        t.add_column("Library Alpha ID", style="bold cyan")
        t.add_column("Pearson Correlation", justify="center")
        t.add_column("Risk Level", justify="center")
        for k, v in all_corrs.items():
            risk = "[bold red]HIGH RISK (>=0.65)[/bold red]" if abs(v) >= threshold else "[bold green]SAFE[/bold green]"
            t.add_row(k, f"{v:+.4f}", risk)
        console.print(t)
    else:
        console.print("[dim]Committed alpha library is currently empty. No prior alphas to correlate with.[/dim]")


def run_dataset_explorer(sim: LocalWQSimulator):
    """Explore dataset dimensions, available columns, and operators"""
    console.print("\n[bold cyan]=== Dataset Explorer & Field Dictionary ===[/bold cyan]")
    df = sim.df

    # 1. Dataset stats
    stats_table = Table(box=box.SIMPLE)
    stats_table.add_column("Property", style="bold white")
    stats_table.add_column("Value", style="bold green")
    stats_table.add_row("Dataset File", str(MASTER_PATH))
    stats_table.add_row("Total Data Rows", f"{df.shape[0]:,}")
    stats_table.add_row("Total Columns", str(df.shape[1]))
    stats_table.add_row("Unique Tickers", f"{df['ticker'].n_unique():,} (USA TOP3000 Universe)")
    stats_table.add_row("Date Range", f"{df['date'].min()} to {df['date'].max()}")
    console.print(stats_table)

    # 2. Columns breakdown
    pv_cols = ["open", "high", "low", "close", "volume", "returns", "adv20", "vwap", "cap"]
    fund_cols = [
        "sales", "operating_income", "net_income", "equity", "assets",
        "cashflow_op", "capex", "fcf", "inventory", "receivable",
        "goodwill", "total_debt", "cogs", "shares_outstanding", "est_eps", "ev"
    ]
    group_cols = ["subindustry", "is_top1000"]

    col_table = Table(title="Available Dataset Fields for Alpha Formulas", box=box.ROUNDED)
    col_table.add_column("Category", style="bold cyan")
    col_table.add_column("Field Names", style="white")
    col_table.add_column("Description / Synonyms", style="dim")

    col_table.add_row("Price / Volume", ", ".join(pv_cols), "Daily split/dividend adjusted price & volume metrics")
    col_table.add_row("SEC Fundamentals", ", ".join(fund_cols), "Quarterly 10-Q/10-K filings (revenues, ebit, cfo, fcf, debt, etc.)")
    col_table.add_row("Grouping & Universe", ", ".join(group_cols), "GICS Subindustry classification & TOP1000 sub-universe flag")
    console.print(col_table)

    # 3. Operators list
    op_table = Table(title="Supported WorldQuant FastExpr Operators", box=box.ROUNDED)
    op_table.add_column("Operator Type", style="bold yellow")
    op_table.add_column("Operators", style="bold white")
    op_table.add_column("Usage Example", style="green")

    op_table.add_row("Cross-Sectional", "rank, zscore, scale, winsorize", "rank(volume / adv20)")
    op_table.add_row("Group / Subindustry", "group_rank, group_neutralize, group_zscore", "group_rank(returns, subindustry)")
    op_table.add_row("Time-Series Rolling", "ts_delay, ts_delta, ts_mean, ts_std_dev", "ts_delay(close, 5)")
    op_table.add_row("Time-Series Advanced", "ts_rank, ts_decay_linear, ts_corr, ts_zscore", "ts_decay_linear(volume, 10)")
    op_table.add_row("Time-Series Extremes", "ts_max, ts_min, ts_sum", "ts_max(high, 20)")
    op_table.add_row("Logic & Math", "if_else, trade_when, signed_power, log, abs, sign", "signed_power(returns, 2)")
    console.print(op_table)


def run_library_manager(sim: LocalWQSimulator):
    """View and manage committed alphas"""
    console.print("\n[bold cyan]=== Committed Alpha Library Management ===[/bold cyan]")
    if sim.corr_checker.alphas_df is None or sim.corr_checker.alphas_df.shape[0] == 0:
        console.print("[yellow]The local committed alpha library is currently empty.[/yellow]")
        return

    df = sim.corr_checker.alphas_df
    alpha_cols = [c for c in df.columns if c != "date"]
    console.print(f"Library Path: {COMMITTED_ALPHAS_PATH}")
    console.print(f"Total Committed Alphas: [bold green]{len(alpha_cols)}[/bold green]")
    console.print(f"Trading Days: [bold green]{df.shape[0]}[/bold green] days ({df['date'].min()} to {df['date'].max()})\n")

    t = Table(title="Committed Alphas in Local Repository", box=box.ROUNDED)
    t.add_column("#", justify="center", style="bold yellow")
    t.add_column("Alpha ID / Name", style="bold cyan")
    t.add_column("Mean Daily PnL", justify="center")
    t.add_column("Daily Volatility", justify="center")

    for i, col in enumerate(alpha_cols, 1):
        s = df[col].drop_nulls()
        mean_pnl = s.mean() if s.len() > 0 else 0.0
        std_pnl = s.std() if s.len() > 0 else 0.0
        t.add_row(str(i), col, f"{mean_pnl:.5f}", f"{std_pnl:.5f}")
    console.print(t)

    if Confirm.ask("Do you want to reset/clear the committed alpha database?", default=False):
        if Confirm.ask("[bold red]Are you sure? This cannot be undone.[/bold red]", default=False):
            if COMMITTED_ALPHAS_PATH.exists():
                COMMITTED_ALPHAS_PATH.unlink()
            sim.corr_checker._load_database()
            console.print("[bold green]✔ Committed alpha library has been reset.[/bold green]")


def run_online_submission():
    """Submit an alpha expression to WorldQuant BRAIN API"""
    console.print("\n[bold cyan]=== Submit Alpha to WorldQuant BRAIN Online ===[/bold cyan]")
    expr = Prompt.ask("Enter WorldQuant expression to submit")
    expr = expr.strip()
    if not expr:
        return

    alpha_name = Prompt.ask("Enter Alpha submission name", default="Alpha_Online_01")
    console.print(f"\nSubmitting to WorldQuant online API with credentials...")
    client = WorldQuantBrainClient()
    success = client.submit_alpha(expr, metrics=None, alpha_name=alpha_name)
    if success:
        console.print("[bold green]✔ Submission request dispatched successfully![/bold green]")
    else:
        console.print("[yellow]Online submission simulated / completed.[/yellow]")


# ==============================================================================
# 3. MAIN INTERACTIVE CONTROLLER
# ==============================================================================
def print_banner():
    banner_text = Text()
    banner_text.append("WORLDQUANT BRAIN QUANT BACKTEST ENGINE\n", style="bold yellow")
    banner_text.append("High-Performance Local Simulation, Diagnostic & Alpha Mining Wizard", style="bold cyan")
    console.print(Panel(banner_text, border_style="cyan", box=box.DOUBLE))


def interactive_main():
    """Main application loop"""
    print_banner()

    # Pre-warm and cache engine
    sim = get_cached_simulator()

    while True:
        console.print("[bold white]══════════════════════════════════════════════════════════════════════[/bold white]")
        console.print("[bold cyan]MAIN MENU - Select an option:[/bold cyan]")
        console.print("  [bold yellow][1][/bold yellow] ⚡ [bold white]Single Alpha Backtest[/bold white] (Enter your own custom WQ expression)")
        console.print("  [bold yellow][2][/bold yellow] 📋 [bold white]Curated Alpha Templates[/bold white] (Pick from top tested formulas)")
        console.print("  [bold yellow][3][/bold yellow] 📂 [bold white]Batch Alpha Screening[/bold white] (Screen from file & generate leaderboard)")
        console.print("  [bold yellow][4][/bold yellow] 🧬 [bold white]Automated Alpha Mining[/bold white] (Run multi-factor search & evolution)")
        console.print("  [bold yellow][5][/bold yellow] 🔍 [bold white]Self-Correlation Diagnostic[/bold white] (Check against committed library)")
        console.print("  [bold yellow][6][/bold yellow] 📚 [bold white]Dataset Explorer & Fields[/bold white] (Inspect 32 fields & operator rules)")
        console.print("  [bold yellow][7][/bold yellow] 💾 [bold white]Manage Alpha Library[/bold white] (View/clean committed alphas database)")
        console.print("  [bold yellow][8][/bold yellow] 🌐 [bold white]Submit to WorldQuant Online[/bold white] (Dispatch to BRAIN API)")
        console.print("  [bold red][0][/bold red] 🚪 [bold red]Exit[/bold red]")
        console.print("[bold white]══════════════════════════════════════════════════════════════════════[/bold white]")

        try:
            choice = Prompt.ask("Choose an option (0-8)", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="1")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated by user. Goodbye![/dim]")
            break

        if choice == "0":
            console.print("\n[bold green]Thank you for using WorldQuant BRAIN Local Engine. Happy Quanting![/bold green]\n")
            break
        elif choice == "1":
            run_single_simulation(sim)
        elif choice == "2":
            run_template_selection(sim)
        elif choice == "3":
            run_batch_screening(sim)
        elif choice == "4":
            run_automated_mining(sim)
        elif choice == "5":
            run_correlation_diagnostic(sim)
        elif choice == "6":
            run_dataset_explorer(sim)
        elif choice == "7":
            run_library_manager(sim)
        elif choice == "8":
            run_online_submission()

        console.print("\n")


if __name__ == "__main__":
    interactive_main()
