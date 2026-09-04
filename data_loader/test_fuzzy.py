import json
from pathlib import Path
from rapidfuzz import fuzz

import os
PROJECT_DIR = Path(__file__).resolve().parent.parent
p = Path(os.environ.get("WQ_FIELDS_JSON", PROJECT_DIR / "data_loader" / "wq_sec_field_alignment.json"))
wq_fields = json.loads(p.read_text(encoding="utf-8"))
f2 = [f for f in wq_fields if f.get("dataset", {}).get("id") == "fundamental2"]

raw_sec_dir = Path(os.environ.get("RAW_SEC_DIR", PROJECT_DIR / "data" / "raw_sec"))
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
