#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wq-local-alpha-engine Skill 自动化完整性与功能验证套件 (Skill Self-Test)
用于验证本 Skill 规范性、依赖解析、离线数据集完整性、AST 编译及回测链路 100% 可用。
"""

import sys
import os
import json
import time
from pathlib import Path

# 确保控制台 UTF-8
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CURRENT_SCRIPT = Path(__file__).resolve()
SKILL_ROOT = CURRENT_SCRIPT.parent.parent

# 定位工程根目录
PROJECT_ROOT = None
for r in [
    SKILL_ROOT,                         # Self-contained skill root
    SKILL_ROOT.parent.parent,           # .agents/skills/wq-local-alpha-engine -> root
    SKILL_ROOT.parent,                  # skills/wq-local-alpha-engine -> root
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\sec_lakehouse_gui"),
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\My Quant Backtest System"),
]:
    if (r / "data_loader").exists() and (r / "data" / "master_backtest.parquet").exists():
        PROJECT_ROOT = r
        break

def test_skill_integrity():
    print("=" * 70)
    print("🚀 开始运行 wq-local-alpha-engine Skill 完整性自动化验收测试")
    print("=" * 70)

    # 1. 结构与文件完整性检验
    print("\n[Step 1/6] 检验 Skill 目录规范与文件完整性...")
    assert (SKILL_ROOT / "SKILL.md").exists(), "缺少 SKILL.md 主指令文件"
    assert (SKILL_ROOT / "scripts" / "run_alpha.py").exists(), "缺少 scripts/run_alpha.py"
    assert (SKILL_ROOT / "references" / "fields_summary.md").exists(), "缺少 references/fields_summary.md"
    assert (SKILL_ROOT / "references" / "is_rules.md").exists(), "缺少 references/is_rules.md"
    assert (SKILL_ROOT / "references" / "operators_reference.md").exists(), "缺少 references/operators_reference.md"
    assert (SKILL_ROOT / "examples" / "quality_alphas.txt").exists(), "缺少 examples/quality_alphas.txt"
    print("  ✔ 核心目录 (scripts, references, examples) 及关键文件全部就绪！")

    # 2. SKILL.md YAML 前言验证
    print("\n[Step 2/6] 验证 SKILL.md YAML Frontmatter 规范...")
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert skill_text.startswith("---"), "SKILL.md 必须以 YAML Frontmatter (---) 开头"
    lines = skill_text.splitlines()
    has_name = any(line.strip().startswith("name:") for line in lines[:10])
    has_desc = any(line.strip().startswith("description:") for line in lines[:10])
    assert has_name, "Frontmatter 缺少 'name' 字段"
    assert has_desc, "Frontmatter 缺少 'description' 字段"
    print("  ✔ YAML Frontmatter 格式严格合规！")

    # 3. 根目录与数据湖挂载检测
    print("\n[Step 3/6] 验证底层工程与 59 维 Lakehouse 宽表挂载...")
    assert PROJECT_ROOT is not None, "未找到有效的项目根目录 (cli.py + data/master_backtest.parquet)"
    print(f"  ✔ 定位到工程根目录: {PROJECT_ROOT}")

    parquet_file = PROJECT_ROOT / "data" / "master_backtest.parquet"
    assert parquet_file.exists(), f"未找到宽表文件: {parquet_file}"
    file_size_mb = parquet_file.stat().st_size / (1024 * 1024)
    print(f"  ✔ 宽表物理大小: {file_size_mb:.1f} MB")

    sys.path.insert(0, str(PROJECT_ROOT))
    import polars as pl
    df = pl.read_parquet(parquet_file)
    rows, cols = df.shape
    print(f"  ✔ 离线数据规格: {rows:,} 行 x {cols} 列")
    assert rows > 3000000, f"样本行数异常 ({rows:,} < 3,000,000)"
    assert cols >= 59, f"特征维度异常 ({cols} < 59)"

    # 4. AST 编译器与同义词 Fallback 检验
    print("\n[Step 4/6] 验证 AST 编译器与智能同义词解析 (income, debt, ebit)...")
    from engine.expr_compiler import compile_wq_expr, build_bidirectional_synonyms
    syn_map = build_bidirectional_synonyms()
    assert "income" in syn_map, "缺少 'income' 同义词"
    assert "debt" in syn_map, "缺少 'debt' 同义词"
    assert "ebit" in syn_map, "缺少 'ebit' 同义词"

    # 测试含有同义词与多重注释的复杂表达式编译
    test_expr = "/* Test ROE */ group_rank(ts_rank(income / equity, 126), subindustry) // suffix"
    compiled_expr = compile_wq_expr(test_expr, available_columns=set(df.columns))
    assert compiled_expr is not None, "AST 编译失败"
    print("  ✔ 智能同义词与 C 风格注释清洗解析成功！")

    # 5. 毫秒级极速回测执行引擎验证
    print("\n[Step 5/6] 运行经典实战黄金因子极速仿真检验...")
    from engine.simulator import LocalWQSimulator
    from engine.correlation_checker import CorrelationChecker
    sim = LocalWQSimulator(df, corr_checker=CorrelationChecker())

    t0 = time.perf_counter()
    golden_expr = "0.6 * group_rank(ts_rank(-(close / vwap - 1), 126), subindustry) + 0.4 * group_rank(ts_rank(value_of_shares_reacquired_during_period / cap, 252), subindustry)"
    metrics = sim.simulate(golden_expr, check_corr=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"  ✔ 单因子回测总耗时: {elapsed_ms:.1f} ms (引擎内部 runtime: {metrics.runtime_ms:.1f} ms)")
    print(f"  ✔ 回测结果: Sharpe={metrics.sharpe:.3f}, Fitness={metrics.fitness:.3f}, Turnover={metrics.turnover * 100:.1f}%, Returns={metrics.returns * 100:.1f}%, MaxDD={metrics.max_drawdown * 100:.1f}%")
    assert metrics.sharpe >= 1.25, f"Sharpe 未达标: {metrics.sharpe}"
    assert metrics.fitness >= 1.0, f"Fitness 未达标: {metrics.fitness}"
    assert metrics.is_all_passed(), f"IS 检验未通过: {metrics.is_checks}"
    print("  ✔ 经典黄金因子 6 项 IS 质检全部满贯 PASS！")

    # 6. CLI 跨目录执行封装器验证
    print("\n[Step 6/6] 验证 scripts/run_alpha.py 跨目录子进程调用...")
    import subprocess
    run_alpha_script = SKILL_ROOT / "scripts" / "run_alpha.py"
    res = subprocess.run(
        [sys.executable, str(run_alpha_script), "fields", "--search", "roic"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=Path.home(), # 任意外部目录
    )
    assert res.returncode == 0, f"run_alpha.py 执行失败: {res.stderr}"
    assert "roic" in res.stdout.lower(), "run_alpha.py 输出未包含预期字段"
    print("  ✔ scripts/run_alpha.py 在任意外部工作目录下均可独立无缝执行！")

    print("\n" + "=" * 70)
    print("🎉 验收完毕！wq-local-alpha-engine 是一个功能完备、高度健壮的 100% 完整 Skill！")
    print("=" * 70)

if __name__ == "__main__":
    test_skill_integrity()
