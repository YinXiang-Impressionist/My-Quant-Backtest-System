import json
from pathlib import Path
from rapidfuzz import fuzz

p = Path(r"C:\Users\xiang\.gemini\config\skills\wq-alpha-research\references\wq_usa_top3000_delay1_data_fields.json")
wq_fields = json.loads(p.read_text(encoding="utf-8"))
f2 = [f for f in wq_fields if f.get("dataset", {}).get("id") == "fundamental2"]

raw_sec_dir = Path(r"C:\Users\xiang\.gemini\antigravity\scratch\wq_local_backtest\data\raw_sec")
sec_labels = {}
for jf in raw_sec_dir.glob("*.json"):
    try:
        content = json.loads(jf.read_text(encoding="utf-8"))
        for tag, info in content.get("facts", {}).get("us-gaap", {}).items():
            if info.get("label"):
                sec_labels[tag] = info.get("label")
    except Exception:
        pass

print(f"Total SEC labeled tags in sample: {len(sec_labels)}")

mapped = 0
for f in f2[:30]:
    desc = f.get("description", "")
    best_score = 0
    best_tag = None
    for tag, label in sec_labels.items():
        score = fuzz.token_set_ratio(desc.lower(), label.lower())
        if score > best_score:
            best_score = score
            best_tag = (tag, label)
    if best_score >= 80:
        mapped += 1
        print(f"WQ ({f['id']}) <--> SEC ({best_tag[0]}): '{best_tag[1]}' [score: {best_score}]")

print(f"Sample 30 fundamental2 fields mapped with score >= 80: {mapped}")
