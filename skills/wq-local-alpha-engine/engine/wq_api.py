"""
WorldQuant BRAIN 线上 API 联动与因子自动提交流水线
功能：
1. 本地初筛达标因子一键构建 WorldQuant 官方规范 Submission Payload；
2. 支持在线提交到 WorldQuant BRAIN (通过 REST API) 或离线安全导出 (JSON/CSV)；
3. 支持保存回测产出的高分因子，构建专属低相关 Alpha 组合。
"""

import os
import json
import csv
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from data_loader.config import DATA_DIR
from .simulator import AlphaMetrics

SUBMISSIONS_DIR = DATA_DIR / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)


class WorldQuantBrainClient:
    """WorldQuant BRAIN 接口客户端"""

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        mock_mode: bool = False
    ):
        self.email = email or os.environ.get("BRAIN_EMAIL", "")
        self.password = password or os.environ.get("BRAIN_PASSWORD", "")
        self.session_token: Optional[str] = None
        self.mock_mode = mock_mode or not bool(self.email and self.password)

    def generate_payload(
        self,
        expression: str,
        universe: str = "TOP3000",
        delay: int = 1,
        neutralization: str = "SUBINDUSTRY",
        truncation: float = 0.08,
    ) -> Dict[str, Any]:
        """构建 WorldQuant 官方标准的 FastExpr 仿真提交字典"""
        return {
            "type": "REGULAR",
            "settings": {
                "instrumentType": "EQUITY",
                "region": "USA",
                "universe": universe,
                "delay": delay,
                "decay": 0,
                "neutralization": neutralization,
                "truncation": truncation,
                "pasteurization": "ON",
                "unitHandling": "VERIFY",
                "nanHandling": "OFF",
                "language": "FASTEXPR",
                "visualization": False,
            },
            "regular": expression.strip(),
        }

    def submit_alpha(
        self,
        expression: str,
        metrics: Optional[AlphaMetrics] = None,
        alpha_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提交 Alpha 表达式至 WorldQuant BRAIN 或落盘离线提交单"""
        payload = self.generate_payload(expression)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = (alpha_name or f"Alpha_{timestamp}").replace(" ", "_")

        if self.mock_mode:
            # 离线模拟落盘
            record = {
                "status": "MOCK_SUBMITTED_OFFLINE",
                "alpha_name": safe_name,
                "timestamp": timestamp,
                "payload": payload,
                "local_metrics": {
                    "sharpe": metrics.sharpe if metrics else None,
                    "fitness": metrics.fitness if metrics else None,
                    "turnover": metrics.turnover if metrics else None,
                    "is_checks": metrics.is_checks if metrics else None,
                }
            }
            out_file = SUBMISSIONS_DIR / f"{safe_name}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
            print(f"[WQ API] (Offline Mode) 因子已生成标准提交包并离线落盘: {out_file}")
            return record

        # 在线官方 API 提交
        url = "https://api.worldquantbrain.com/simulations"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WQQuantResearch LocalEngine/2.0"
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

        # 身份验证 (Basic Auth 或 Session Token)
        import base64
        creds = f"{self.email}:{self.password}"
        b64_creds = base64.b64encode(creds.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {b64_creds}")

        try:
            with urllib.request.urlopen(req) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                print(f"[WQ API] 线上提交成功！返回信息: {resp_data}")
                return resp_data
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            print(f"[WQ API] 提交失败 (HTTP {e.code}): {err_msg}")
            return {"status": "ERROR", "code": e.code, "message": err_msg}
        except Exception as e:
            print(f"[WQ API] 提交异常: {e}")
            return {"status": "EXCEPTION", "message": str(e)}


def export_alphas_to_csv(alphas_list: List[Dict[str, Any]], output_path: Path):
    """将批量筛选出的达标因子导出为标准 CSV 清单"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "expression", "sharpe", "fitness", "turnover", "sub_universe_sharpe", "status"])
        for a in alphas_list:
            m: AlphaMetrics = a["metrics"]
            writer.writerow([
                a.get("id", ""),
                a.get("expression", ""),
                m.sharpe,
                m.fitness,
                m.turnover,
                m.sub_universe_sharpe,
                "PASS" if m.is_all_passed() else "FAIL"
            ])
    print(f"[WQ Exporter] 成功导出 {len(alphas_list)} 个因子至: {output_path}")
