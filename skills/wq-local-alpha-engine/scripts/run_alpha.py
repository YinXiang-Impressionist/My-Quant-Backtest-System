#!/usr/bin/env python
"""
WorldQuant BRAIN 本地极速量化引擎 - 跨目录执行封装器
支持在任意当前工作目录 (cwd) 下无缝调用本项目的本地回测引擎与初筛工具。
"""

import sys
from pathlib import Path

# 自动推导项目根目录
CURRENT_FILE = Path(__file__).resolve()
# 优先相对当前 skill 目录定位根目录
POSSIBLE_ROOTS = [
    CURRENT_FILE.parent.parent.parent.parent, # .agents/skills/wq-local-alpha-engine/scripts -> root
    CURRENT_FILE.parent.parent.parent,        # skills/wq-local-alpha-engine/scripts -> root
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\sec_lakehouse_gui"),
    Path(r"d:\AAA Every Coding Project\Quant Backtest Project\My Quant Backtest System"),
    Path(r"d:\My Quant Backtest System"),
]

PROJECT_ROOT = None
for r in POSSIBLE_ROOTS:
    if (r / "cli.py").exists() and (r / "data_loader").exists():
        PROJECT_ROOT = r
        break

if not PROJECT_ROOT:
    raise FileNotFoundError("未能自动定位到 'My Quant Backtest System' 项目根目录，请检查项目路径。")

sys.path.insert(0, str(PROJECT_ROOT))

# 直接导入并执行 cli 主程序
from cli import main

if __name__ == "__main__":
    main()
