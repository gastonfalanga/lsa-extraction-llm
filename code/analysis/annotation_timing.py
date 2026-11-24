import csv
import datetime as dt
import os
import sys

from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(__file__))
from baseline_numbers import load

SCRATCH_SHEET = "work/annotation/returned/annotation_completed.xlsx"
SCRATCH_KEY = "work/annotation/key.csv"
SAMPLE = "work/audit/audit_sample.csv"
AUDIT_TIMING = "work/audit/results/timing.csv"
HANDS = ("dominant_hand", "non_dominant_hand")


def units(sign):
    return sum(1 for v in sign.get("sign_variants", []) for c in v.get("sequential_components", [])
               for h in HANDS if (c.get(h) or {}).get("initial_position"))


def main():
    signs, _ = load()
    by_id = {s["sign_id"]: s for s in signs}
    with open(SCRATCH_KEY, encoding="utf-8") as f:
        scratch_ids = [r["ocr_id"] for r in csv.DictReader(f)]
    with open(SAMPLE, encoding="utf-8-sig") as f:
        audit_ids = [r["ocr_id"] for r in csv.DictReader(f) if r.get("set", "main") == "main"]

    wb = load_workbook(SCRATCH_SHEET, read_only=True)
    seconds = 0
    for r in wb["timing"].iter_rows(min_row=2, values_only=True):
        if r[2] and r[3]:
            seconds += (dt.datetime.combine(dt.date.min, r[3]) - dt.datetime.combine(dt.date.min, r[2])).seconds
    annotated = sum(1 for r in wb["annotation"].iter_rows(min_row=2, values_only=True)
                    if r[0] is not None and any(x not in (None, "") for x in r[5:20]))

    with open(AUDIT_TIMING, encoding="utf-8") as f:
        t = {(r["phase"], r["task"]): float(r["seconds_per_sign"]) for r in csv.DictReader(f)}
    audit_per_sign = t[("main", "text")] + t[("dictation", "dictation")]

    u_scratch = sum(units(by_id[i]) for i in scratch_ids)
    u_audit = sum(units(by_id[i]) for i in audit_ids)
    u_all = sum(units(s) for s in signs)
    per_unit_annot = seconds / u_scratch
    per_unit_audit = audit_per_sign / (u_audit / len(audit_ids))
    print(f"Annotation from scratch: {len(scratch_ids)} signs, {seconds / 60:.0f} min, {seconds / len(scratch_ids):.0f} s per sign")
    print(f"hands to describe per sign: from scratch {u_scratch / len(scratch_ids):.2f} ({u_scratch}), audit sample "
          f"{u_audit / len(audit_ids):.2f} ({len(audit_ids)} signs), dictionary {u_all / len(signs):.2f} ({u_all})")
    print(f"rows filled by the annotator: {annotated}")
    print(f"seconds per hand: annotation from scratch {per_unit_annot:.1f}, blind audit {per_unit_audit:.1f} "
          f"({audit_per_sign:.1f} s per sign)")
    print(f"whole dictionary by hand at that pace: {u_all * per_unit_annot / 3600:.1f} h")


if __name__ == "__main__":
    main()
