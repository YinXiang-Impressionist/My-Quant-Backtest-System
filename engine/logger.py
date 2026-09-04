# -*- coding: utf-8 -*-
"""
WorldQuant BRAIN 本地研发流水账日志记录器 (Workspace Research Logger)
核心原则：
1. 强制在【用户当前工作目录】(Path.cwd() / "logs") 下持久化记录；
2. 零污染 Skill 目录与中央引擎；
3. 结构化记录每一次单因子回测、批量初筛、自动挖掘及异常报错。
"""

import sys
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from data_loader.config import LOGS_DIR, ensure_workspace_dirs


def get_daily_log_file() -> Path:
    """获取当前工作目录下的当日流水日志文件"""
    ensure_workspace_dirs()
    date_str = datetime.now().strftime("%Y%m%d")
    return LOGS_DIR / f"alpha_research_{date_str}.log"


def get_error_log_file() -> Path:
    """获取当前工作目录下的错误日志文件"""
    ensure_workspace_dirs()
    return LOGS_DIR / "error.log"


def log_research_event(
    event_type: str,
    expression: str,
    metrics: Any,
    alpha_id: Optional[str] = None,
    extra_notes: Optional[str] = None,
):
    """
    记录单次回测/初筛事件到工作目录流水日志
    """
    try:
        log_file = get_daily_log_file()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        status_str = "PASS" if (hasattr(metrics, "is_all_passed") and metrics.is_all_passed()) else "FAIL"
        sharpe_str = f"{metrics.sharpe:+.3f}" if hasattr(metrics, "sharpe") else "N/A"
        fitness_str = f"{metrics.fitness:+.3f}" if hasattr(metrics, "fitness") else "N/A"
        turnover_str = f"{metrics.turnover*100:5.1f}%" if hasattr(metrics, "turnover") else "N/A"
        returns_str = f"{metrics.returns*100:+5.1f}%" if hasattr(metrics, "returns") else "N/A"
        maxdd_str = f"{metrics.max_drawdown*100:4.1f}%" if hasattr(metrics, "max_drawdown") else "N/A"
        runtime_str = f"{metrics.runtime_ms:.1f}ms" if hasattr(metrics, "runtime_ms") else "N/A"

        line = (
            f"[{now_str}] [{event_type.upper():<10}] [{status_str}] "
            f"ID: {alpha_id or 'N/A'} | Sharpe: {sharpe_str} | Fitness: {fitness_str} | "
            f"TO: {turnover_str} | Ret: {returns_str} | MaxDD: {maxdd_str} | Speed: {runtime_str} | "
            f"Expr: {expression}"
        )
        if extra_notes:
            line += f" | Notes: {extra_notes}"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        # 日志记录失败不阻塞核心计算
        sys.stderr.write(f"[Logger Warning] 无法写入工作区日志: {e}\n")


def log_error(context: str, exc: Optional[Exception] = None):
    """
    记录异常回溯堆栈到工作目录 error.log
    """
    try:
        err_file = get_error_log_file()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_str = traceback.format_exc() if exc else ""

        with open(err_file, "a", encoding="utf-8") as f:
            f.write(f"[{now_str}] [ERROR] Context: {context}\n")
            if exc:
                f.write(f"Exception: {type(exc).__name__}: {exc}\n")
            if tb_str.strip() and tb_str.strip() != "NoneType: None":
                f.write(tb_str + "\n")
            f.write("-" * 80 + "\n")
    except Exception:
        pass
