"""
SEC 官方 companyfacts.zip 全量历史快照多进程流式解析器
功能：
1. 直接读取 SEC 官方发布的 companyfacts.zip (1.34GB 全量公司历史财报)；
2. 采用多进程 (multiprocessing.Pool) 并行解析 JSON；
3. 严格基于 US-GAAP XBRL 标签抽取三张表法定科目；
4. 严格保留正式法定披露日 'filed'，阻断未来函数；
5. 向量化落盘为 Parquet 离线数据库。
"""

import io
import json
import zipfile
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Any, Optional
import polars as pl
from .config import DATA_DIR, FUND_PATH, XBRL_TAGS, SUBINDUSTRY_MAPPING


def extract_pit_records_from_facts(
    ticker_or_cik: str,
    facts: Dict[str, Any],
    tag_map: Dict[str, List[str]] = XBRL_TAGS
) -> List[Dict[str, Any]]:
    """从单家公司 Facts JSON 结构中抽取 10-K / 10-Q PIT 记录"""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    if not us_gaap:
        return []

    entity_name = facts.get("entityName", "")
    records = []

    for wq_field, tags in tag_map.items():
        for tag in tags:
            if tag in us_gaap:
                units = us_gaap[tag].get("units", {})
                # 通常三张表数值单位为 USD，股数为 shares / pure
                unit_items = units.get("USD", []) or units.get("shares", []) or units.get("pure", [])
                for item in unit_items:
                    form = item.get("form", "")
                    if form in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
                        filed_date = item.get("filed")
                        end_date = item.get("end")
                        val = item.get("val")
                        if filed_date and val is not None:
                            try:
                                records.append({
                                    "ticker": ticker_or_cik,
                                    "field": wq_field,
                                    "filed_date": str(filed_date),
                                    "end_date": str(end_date),
                                    "form": str(form),
                                    "value": float(val),
                                })
                            except (ValueError, TypeError):
                                continue
                # 匹配到一个标准 tag 后跳出，避免同义标签重复计数
                break
    return records


def _process_zip_entry(args) -> List[Dict[str, Any]]:
    """多进程工作子任务：解压并抽取单个 JSON 文件"""
    zip_path_str, filename, cik_ticker_map = args
    try:
        with zipfile.ZipFile(zip_path_str, "r") as zf:
            content = zf.read(filename).decode("utf-8")
            data = json.loads(content)
            
            cik_int = data.get("cik")
            ticker = cik_ticker_map.get(cik_int, f"CIK_{cik_int:010d}") if cik_ticker_map else f"CIK_{cik_int:010d}"
            return extract_pit_records_from_facts(ticker, data)
    except Exception:
        return []


class SECCompanyFactsZipParser:
    """SEC 全量快照解析管道"""

    def __init__(self, zip_path: Optional[Path] = None, cik_ticker_map: Optional[Dict[int, str]] = None):
        self.zip_path = zip_path or (DATA_DIR / "companyfacts.zip")
        self.cik_ticker_map = cik_ticker_map or {}

    def parse_and_export(
        self,
        output_parquet: Path = FUND_PATH,
        num_workers: int = 4,
        limit_files: Optional[int] = None
    ) -> pl.DataFrame:
        """多进程流式解析 zip 文件并转存为 Parquet"""
        if not self.zip_path.exists():
            raise FileNotFoundError(f"SEC companyfacts.zip 未在路径找到: {self.zip_path}")

        print(f"[SEC Zip Parser] 正在读取压缩包索引: {self.zip_path}...")
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            json_filenames = [name for name in zf.namelist() if name.endswith(".json")]

        if limit_files:
            json_filenames = json_filenames[:limit_files]

        total_files = len(json_filenames)
        print(f"[SEC Zip Parser] 发现 {total_files} 个公司财报快照，正在启动 {num_workers} 进程并行抽取...")

        tasks = [
            (str(self.zip_path), fname, self.cik_ticker_map)
            for fname in json_filenames
        ]

        all_records = []
        with mp.Pool(processes=num_workers) as pool:
            for i, res in enumerate(pool.imap_unordered(_process_zip_entry, tasks, chunksize=100)):
                if res:
                    all_records.extend(res)
                if (i + 1) % 1000 == 0 or (i + 1) == total_files:
                    print(f"  -> 已处理 {i + 1}/{total_files} 个公司快照，累计抽取记录: {len(all_records)} 条")

        if not all_records:
            print("[SEC Zip Parser] 警告: 未抽取到任何记录。")
            return pl.DataFrame()

        print("[SEC Zip Parser] 正在转换为 Polars 宽表结构...")
        df = pl.DataFrame(all_records)
        df = df.with_columns([
            pl.col("filed_date").str.to_date("%Y-%m-%d"),
            pl.col("end_date").str.to_date("%Y-%m-%d"),
        ])

        output_parquet.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(output_parquet)
        print(f"[SEC Zip Parser] 成功落盘 {df.shape[0]} 条法定财报记录到: {output_parquet}")
        return df


if __name__ == "__main__":
    parser = SECCompanyFactsZipParser()
    if parser.zip_path.exists():
        parser.parse_and_export()
    else:
        print(f"提示: {parser.zip_path} 不存在。如需下载，请使用 SEC 官方链接: https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip")
