import csv
import json
import os
import subprocess
from collections import Counter

from jsonschema import Draft7Validator

PER_BATCH_CSV = "work/raw_ocr_history/per_batch.csv"
SCHEMA_CANDIDATES = ["schema.json", "schemas/schema.json", "schemas/schema.sign.json"]
OUT = "work/outputs/schema_conformance/conformance.csv"


def git_show(commit, path):
    r = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main():
    rows, kinds, totals = [], Counter(), Counter()
    with open(PER_BATCH_CSV, encoding="utf-8-sig") as f:
        batches = [b for b in csv.DictReader(f) if b["batch"] != "lote_156.json"]
    for b in batches:
        commit = b["first_commit"]
        schema_text = next((t for t in (git_show(commit, p) for p in SCHEMA_CANDIDATES) if t), None)
        batch_text = git_show(commit, f"data/processed/{b['batch']}") or git_show(commit, f"data/{b['batch']}")
        if schema_text is None or batch_text is None:
            rows.append([b["batch"], commit, "", "", "", "missing schema or batch at commit"])
            continue
        validator = Draft7Validator(json.loads(schema_text))
        signs = json.loads(batch_text)
        bad = 0
        for sign in signs:
            errors = list(validator.iter_errors(sign))
            if errors:
                bad += 1
                for e in errors:
                    kinds[(e.validator, str(e.instance)[:40])] += 1
        totals["signs"] += len(signs)
        totals["invalid"] += bad
        rows.append([b["batch"], commit, len(signs), bad, round(100 * (len(signs) - bad) / len(signs), 1), ""])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["batch", "commit", "signs", "invalid_signs", "valid_%", "note"])
        w.writerows(rows)
    clean = sum(1 for r in rows if r[3] == 0)
    print(f"batches: {len(rows)}; fully valid: {clean}; signs: {totals['signs']}; invalid signs: {totals['invalid']}")
    print("error kinds:", kinds.most_common())
    print("skipped:", [r[0] for r in rows if r[5]])


if __name__ == "__main__":
    main()
