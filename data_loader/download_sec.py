"""
SEC EDGAR 官方原版三张表批量下载与离线缓存器
功能：
- 严格基于法定 XBRL 标签 (OperatingIncomeLoss, Assets, StockholdersEquity 等)
- 保留真实的正式披露日期 'filed'，彻底防止未来函数 (Point-in-Time 对齐)
- 自动遵守 SEC 官方 10 requests/second 速率规范
- 落盘为本地 JSON 缓存与 fundamentals.parquet
"""

import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional
import polars as pl

from .config import (
    DATA_DIR,
    RAW_SEC_DIR,
    FUND_PATH,
    SEC_HEADERS,
    XBRL_TAGS,
    SUBINDUSTRY_MAPPING,
)

# 默认 CIK 映射字典
DEFAULT_CIK_MAP: Dict[str, int] = {
    "AAPL": 320193, "MSFT": 789019, "NVDA": 1045810, "AMZN": 1018724,
    "GOOGL": 1652044, "META": 1326801, "TSLA": 1318605, "JPM": 19617,
    "JNJ": 200406, "XOM": 34088, "WMT": 104169, "BAC": 70858,
    "COST": 909832, "MCD": 63908, "AMD": 2488, "INTC": 50863,
    "QCOM": 804328, "TXN": 97476, "DIS": 1744489, "NKE": 320187,
    "AVGO": 1730168, "ORCL": 1341439, "CRM": 1108524, "ADBE": 796343,
    "NFLX": 1065280, "HD": 354950, "PG": 80424, "KO": 21344,
    "PEP": 77476, "V": 1403161, "MA": 1141391, "UNH": 731766,
    "LLY": 59478, "PFE": 78003, "CVX": 93410, "CAT": 18230,
}


def fetch_sec_company_facts(
    cik: int,
    raw_dir: Path = RAW_SEC_DIR,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """从 SEC 下载单个公司的完整原始 XBRL Facts JSON 并离线缓存"""
    cik_10 = f"{cik:010d}"
    cache_file = raw_dir / f"CIK{cik_10}.json"
    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_10}.json"
    req = urllib.request.Request(url, headers=SEC_HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            time.sleep(0.12)  # 严格遵守 SEC 10 requests/s 规范
            return data
    except Exception as e:
        print(f"Warning: Failed fetching SEC facts for CIK {cik}: {e}")
        return {}


def parse_sec_facts_to_pit_records(ticker: str, facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提取 10-Q/10-K 原版数据并保留精确法定披露日 'filed'"""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    if not us_gaap:
        return []

    records = []
    for wq_field, tags in XBRL_TAGS.items():
        for tag in tags:
            if tag in us_gaap:
                units = us_gaap[tag].get("units", {})
                usd_items = units.get("USD", []) or units.get("shares", []) or units.get("pure", [])
                for item in usd_items:
                    form = item.get("form", "")
                    if form in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
                        filed_date = item.get("filed")  # 正式法定公开发布日期！
                        end_date = item.get("end")      # 财报截止日
                        val = item.get("val")
                        if filed_date and val is not None:
                            try:
                                records.append({
                                    "ticker": ticker,
                                    "field": wq_field,
                                    "filed_date": str(filed_date),
                                    "end_date": str(end_date),
                                    "form": str(form),
                                    "value": float(val)
                                })
                            except (ValueError, TypeError):
                                continue
                break  # 匹配到一个标准 tag 后不再继续匹配备用 tag
    return records


def download_offline_fundamentals(
    cik_map: Optional[Dict[str, int]] = None,
    output_path: Path = FUND_PATH,
    raw_dir: Path = RAW_SEC_DIR,
    force_refresh: bool = False
) -> pl.DataFrame:
    """批量下载并解析 SEC EDGAR 三张表"""
    target_cik_map = cik_map or DEFAULT_CIK_MAP
    raw_dir.mkdir(parents=True, exist_ok=True)
    all_records = []
    print(f"[SEC Downloader] 开始批量处理 {len(target_cik_map)} 只标的的 SEC 官方原始三张表...")

    for ticker, cik in target_cik_map.items():
        facts = fetch_sec_company_facts(cik, raw_dir, force_refresh=force_refresh)
        records = parse_sec_facts_to_pit_records(ticker, facts)
        all_records.extend(records)

    if not all_records:
        print("[SEC Downloader] 未提取到财报记录。")
        return pl.DataFrame()

    df = pl.DataFrame(all_records)
    print(f"[SEC Downloader] 抽取完成！共获取 {df.shape[0]} 条法定财报条目。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    print(f"[SEC Downloader] 已保存到离线 Parquet: {output_path}")
    return df


if __name__ == "__main__":
    download_offline_fundamentals()
