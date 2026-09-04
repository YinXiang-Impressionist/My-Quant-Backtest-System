"""
WorldQuant BRAIN Local Alpha Simulator - Lightweight GUI Server
Zero external web dependencies. Built using Python's standard library `http.server`.

Usage:
    python gui.py
    python -m cli gui --port 8888
"""

import sys
import os
import json
import time
import mimetypes
import webbrowser
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

# Windows UTF-8 encoding safeguard
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import numpy as np

from data_loader.config import MASTER_PATH, COMMITTED_ALPHAS_PATH
from data_loader.build_master_dataset import build_master_dataset
from engine.simulator import LocalWQSimulator, AlphaMetrics
from engine.correlation_checker import CorrelationChecker
from engine.wq_api import WorldQuantBrainClient
from run import CURATED_ALPHAS

STATIC_DIR = BASE_DIR / "gui_static"

# Global cached simulator instance for instantaneous (<20ms) simulations
_CACHED_SIMULATOR: Optional[LocalWQSimulator] = None


def get_simulator() -> LocalWQSimulator:
    global _CACHED_SIMULATOR
    if _CACHED_SIMULATOR is not None:
        return _CACHED_SIMULATOR

    if not MASTER_PATH.exists():
        print(f"[Engine] 未检测到宽表: {MASTER_PATH}，正在触发自动构建...")
        build_master_dataset()

    print(f"[Engine] 正在热加载 345 万行历史宽表至内存...")
    t0 = time.perf_counter()
    df = pl.read_parquet(MASTER_PATH)
    corr_checker = CorrelationChecker()
    _CACHED_SIMULATOR = LocalWQSimulator(df, corr_checker=corr_checker)
    t_load = (time.perf_counter() - t0) * 1000
    print(f"[Engine] ✔ 内存极速引擎已就绪 ({t_load:.1f} ms)！共 {df.shape[0]:,} 行，{df['ticker'].n_unique()} 只成分股。")
    return _CACHED_SIMULATOR


class WQGuiRequestHandler(BaseHTTPRequestHandler):
    """WorldQuant BRAIN GUI HTTP & REST API Request Handler"""

    server_version = "WQLocalEngine/2.0"

    def do_GET(self):
        url_path = self.path.split("?")[0]

        # 1. API: Engine Status
        if url_path == "/api/status":
            sim = get_simulator()
            payload = {
                "status": "ready",
                "rows": sim.df.shape[0],
                "columns": sim.df.shape[1],
                "stocks": sim.df["ticker"].n_unique(),
                "min_date": str(sim.df["date"].min()),
                "max_date": str(sim.df["date"].max()),
            }
            self.send_json_response(payload)
            return

        # 2. API: Curated Templates
        if url_path == "/api/templates":
            payload = {"templates": CURATED_ALPHAS}
            self.send_json_response(payload)
            return

        # 3. Favicon handling
        if url_path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 4. Static Files Serving
        if url_path == "/" or url_path == "/index.html":
            file_path = STATIC_DIR / "index.html"
        else:
            rel_path = url_path.lstrip("/")
            file_path = STATIC_DIR / rel_path

        # Defensive check against directory traversal
        try:
            resolved = file_path.resolve()
            if not resolved.is_relative_to(STATIC_DIR.resolve()) or not resolved.is_file():
                self.send_error(404, "File Not Found")
                return
        except Exception:
            self.send_error(404, "File Not Found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Internal Error: {e}")

    def do_POST(self):
        url_path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self.send_json_response({"error": "Invalid JSON payload"}, status=400)
            return

        # 1. API: Simulation
        if url_path == "/api/simulate":
            expression = body.get("expression", "").strip()
            if not expression:
                self.send_json_response({"error": "Missing expression"}, status=400)
                return

            delay = int(body.get("delay", 1))
            decay = int(body.get("decay", 0))
            neutralization = body.get("neutralization", "SUBINDUSTRY")
            truncation = float(body.get("truncation", 0.08))
            alpha_id = body.get("alpha_id", "Alpha_01")
            check_corr = bool(body.get("check_corr", True))

            try:
                sim = get_simulator()
                metrics = sim.simulate(
                    expression=expression,
                    delay=delay,
                    decay=decay,
                    neutralization=neutralization,
                    truncation=truncation,
                    alpha_id=alpha_id,
                    check_corr=check_corr,
                )

                # Format daily pnl and dates (downsample if over 1500 days for snappy charting)
                dates = [str(d)[:10] for d in metrics.daily_dates]
                pnl = [round(float(x), 6) for x in metrics.daily_pnl.tolist()]

                result_payload = {
                    "alpha_id": alpha_id,
                    "expression": expression,
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
                    "daily_dates": dates,
                    "daily_pnl": pnl,
                }
                self.send_json_response(result_payload)
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        # 2. API: Commit Alpha
        if url_path == "/api/commit":
            alpha_id = body.get("alpha_id", "Committed_Alpha")
            expression = body.get("expression", "")
            try:
                sim = get_simulator()
                metrics = sim.simulate(expression, check_corr=False)
                if metrics.daily_pnl.size > 0:
                    sim.corr_checker.commit_alpha(alpha_id, metrics.daily_dates, metrics.daily_pnl)
                    self.send_json_response({"status": "ok", "message": f"Alpha '{alpha_id}' committed."})
                else:
                    self.send_json_response({"error": "Insufficient PnL data to commit."}, status=400)
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        # 3. API: Submit to WorldQuant Online
        if url_path == "/api/submit":
            alpha_id = body.get("alpha_id", "Submitted_Alpha")
            expression = body.get("expression", "")
            try:
                sim = get_simulator()
                metrics = sim.simulate(expression, check_corr=False)
                client = WorldQuantBrainClient()
                res = client.submit_alpha(expression, metrics, alpha_name=alpha_id)
                self.send_json_response({"status": "ok", "result": res})
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        self.send_error(404, "Endpoint Not Found")

    def send_json_response(self, data: Dict[str, Any], status: int = 200):
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(json_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json_bytes)

    def log_message(self, format, *args):
        # Concise and exception-safe logging
        try:
            msg = format % args
            if any(k in msg for k in ["/api/simulate", "/api/commit", "/api/status", "500"]):
                print(f"[GUI Server] {self.address_string()} - {msg}")
        except Exception:
            pass


def start_gui(host: str = "127.0.0.1", port: int = 8888, open_browser: bool = True):
    """启动极速轻量 GUI 服务器"""
    # 预加载仿真引擎
    get_simulator()

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, WQGuiRequestHandler)
    url = f"http://{host}:{port}"

    print(f"\n" + "=" * 65)
    print(f"🚀 WorldQuant BRAIN 本地轻量化量化回测与因子仿真 GUI 已启动!")
    print(f"🌐 访问地址: {url}")
    print(f"⚙  特性: 纯净零冗余，极速 (<20ms) 响应，支持热修改参数与 IS 红线质检")
    print(f"=" * 65 + "\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[GUI Server] 服务已正常终止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN 本地图形化回测界面")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="服务端口号 (默认: 8888)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    start_gui(host=args.host, port=args.port, open_browser=not args.no_browser)
