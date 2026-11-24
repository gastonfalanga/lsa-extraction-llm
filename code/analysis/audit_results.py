import csv
import math
import os
import subprocess
from collections import Counter, defaultdict

from openpyxl import load_workbook

WORKBOOK = "work/audit/audit_sheet.xlsx"
SAMPLE_CSV = "work/audit/audit_sample.csv"
PER_BATCH_CSV = "work/raw_ocr_history/per_batch.csv"
PROMPT_PATH = "prompts/scan_pdf.md"
OUT_DIR = "work/audit/results"
FIRST_PASS_CSV = "work/audit/recheck_1-4_first_pass.csv"
FIRST_DICTATION_ROW = 12

WRITTEN = ["initial_configuration", "final_configuration", "movement_manner", "movement_path",
           "movement_contact", "movement_repetition", "non_manual_components"]
DRAWN = ["initial_position", "initial_orientation", "final_position", "final_orientation"]
SIGN_LEVEL = [("hand_count", 11), ("variant_count", 14), ("component_counts", 17)]
JUDGED = {"Correct", "Wrong"}
NON_ERROR = ["Ambiguous in source", "Source inconsistent", "Not applicable"]


def wilson(p, n, z=1.96):
    if n <= 0:
        return (float("nan"), float("nan"))
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def estimate(items):
    n = len(items)
    if n == 0:
        return [0, 0, "", "", "", ""]
    correct = sum(1 for _, ok in items if ok)
    sw = sum(w for w, _ in items)
    p = sum(w for w, ok in items if ok) / sw
    n_eff = sw * sw / sum(w * w for w, _ in items)
    lo, hi = wilson(p, n_eff)
    return [n, correct, round(100 * correct / n, 1), round(100 * p, 1), round(100 * lo, 1), round(100 * hi, 1)]


def prompt_versions():
    log = subprocess.run(["git", "log", "--follow", "--format=%h %ct %ad", "--date=format:%m-%d", "--", PROMPT_PATH],
                         capture_output=True, text=True, check=True).stdout.split("\n")
    revisions = sorted((int(ct), h, d) for h, ct, d in (l.split() for l in log if l.strip()))
    out = {}
    with open(PER_BATCH_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ct = int(subprocess.run(["git", "show", "-s", "--format=%ct", row["first_commit"]],
                                    capture_output=True, text=True, check=True).stdout.strip())
            in_force = [r for r in revisions if r[0] <= ct]
            batch = "v1_" + row["batch"].replace(".json", ".pdf")
            out[batch] = f"{in_force[-1][2]} ({in_force[-1][1]})" if in_force else "before first revision"
    return out


def confidence_bin(c):
    c = float(c)
    if c <= 0.65:
        return "a: <=0.65"
    if c <= 0.75:
        return "b: 0.70-0.75"
    if c <= 0.80:
        return "c: 0.80"
    return "d: >=0.85"


def main():
    with open(SAMPLE_CSV, encoding="utf-8-sig") as f:
        sample = {r["ocr_id"]: r for r in csv.DictReader(f)}
    wb = load_workbook(WORKBOOK, read_only=True)
    signs = {}
    for i, r in enumerate(wb["signs"].iter_rows(min_row=2, values_only=True), start=2):
        if r[1]:
            signs[r[1]] = {"row": i, "set": r[0], "values": r,
                           "method": "excel" if i < FIRST_DICTATION_ROW else "dictation"}
    main_ids = [k for k, v in signs.items() if v["set"] == "main"]
    for k in main_ids:
        values = list(signs[k]["values"])
        assert values[18] == "Yes", f"{k} not reviewed"
        for _, col in SIGN_LEVEL:
            if values[col - 1] in (None, ""):
                values[col - 1] = "Correct"
        signs[k]["values"] = values
    assert len(main_ids) == 150, len(main_ids)

    fields = [r for r in wb["fields"].iter_rows(min_row=2, values_only=True) if r[1] in main_ids]
    weight = {k: float(sample[k]["weight"]) for k in main_ids}

    by_field, by_group, non_error = [], [], Counter()
    for method in ("excel", "dictation", "pooled"):
        def rows(pred):
            return [(weight[r[1]], r[8] == "Correct") for r in fields
                    if r[8] in JUDGED and pred(r) and (method == "pooled" or signs[r[1]]["method"] == method)]
        for field in WRITTEN + DRAWN:
            by_field.append([method, "written" if field in WRITTEN else "drawing only", field]
                            + estimate(rows(lambda r, f=field: r[6] == f)))
        for group, members in (("written", WRITTEN), ("drawing only", DRAWN)):
            by_group.append([method, group] + estimate(rows(lambda r, m=members: r[6] in m)))
    for r in fields:
        if r[8] in NON_ERROR:
            non_error[(r[8], "written" if r[6] in WRITTEN else "drawing only")] += 1

    sign_rows = []
    wrong_signs = set(r[1] for r in fields if r[8] == "Wrong")
    for method in ("excel", "dictation", "pooled"):
        ids = [k for k in main_ids if method == "pooled" or signs[k]["method"] == method]
        for name, col in SIGN_LEVEL:
            items = [(weight[k], signs[k]["values"][col - 1] == "Correct") for k in ids
                     if signs[k]["values"][col - 1] in JUDGED]
            sign_rows.append([method, name] + estimate(items))
        whole = []
        for k in ids:
            bad = k in wrong_signs or any(signs[k]["values"][c - 1] == "Wrong" for _, c in SIGN_LEVEL)
            whole.append((weight[k], not bad))
        sign_rows.append([method, "whole sign correct"] + estimate(whole))

    errors = Counter()
    gaps = Counter()
    for r in fields:
        if r[8] == "Wrong":
            errors[(signs[r[1]]["method"], r[11] or "(none)")] += 1
        if r[12] == "Yes":
            gaps[(signs[r[1]]["method"], r[6])] += 1
    tags = Counter()
    for k in main_ids:
        note = (signs[k]["values"][20] or "")
        for tag in ("[missing hand]", "[spurious variant]", "[spurious component]", "[undrawn variant]", "[order]"):
            if tag in note:
                tags[tag] += 1
    for r in fields:
        for tag in ("[spurious component]", "[spurious variant]", "[undrawn variant]"):
            if r[13] and tag in r[13]:
                tags[tag + " (field rows)"] += 1

    versions = prompt_versions()
    calib, by_version = defaultdict(list), defaultdict(list)
    for k in main_ids:
        if signs[k]["method"] != "dictation":
            continue
        judged = [r for r in fields if r[1] == k and r[8] in JUDGED]
        wrong = sum(1 for r in judged if r[8] == "Wrong")
        whole_ok = k not in wrong_signs and not any(signs[k]["values"][c - 1] == "Wrong" for _, c in SIGN_LEVEL)
        calib[confidence_bin(sample[k]["ocr_confidence"])].append((len(judged), wrong, whole_ok))
        by_version[versions.get(sample[k]["source_batch_file"], "?")].append((len(judged), wrong, whole_ok))

    def summarize(groups):
        out = []
        for key in sorted(groups):
            g = groups[key]
            n_fields, n_wrong = sum(x[0] for x in g), sum(x[1] for x in g)
            ok = sum(1 for x in g if x[2])
            lo, hi = wilson(ok / len(g), len(g))
            out.append([key, len(g), n_fields, n_wrong, round(100 * n_wrong / n_fields, 1),
                        ok, round(100 * ok / len(g), 1), round(100 * lo, 1), round(100 * hi, 1)])
        return out
    calib_rows, version_rows = summarize(calib), summarize(by_version)
    conf = [(float(sample[k]["ocr_confidence"]),
             sum(1 for r in fields if r[1] == k and r[8] == "Wrong") /
             max(1, sum(1 for r in fields if r[1] == k and r[8] in JUDGED)))
            for k in main_ids if signs[k]["method"] == "dictation"]
    mx, my = sum(c for c, _ in conf) / len(conf), sum(e for _, e in conf) / len(conf)
    cov = sum((c - mx) * (e - my) for c, e in conf)
    r_conf = cov / math.sqrt(sum((c - mx) ** 2 for c, _ in conf) * sum((e - my) ** 2 for _, e in conf))

    timing = defaultdict(lambda: [0, 0])
    for r in list(wb["timing"].iter_rows(min_row=2, values_only=True)):
        batch, task, n, secs = r[0], r[1], r[2], r[3]
        if batch == "pilot":
            phase = "pilot"
        elif task == "text":
            phase = "main"
        elif task == "visual":
            phase = "excel pass (superseded by dictation)"
        else:
            phase = "dictation"
        timing[(phase, task)][0] += n
        timing[(phase, task)][1] += secs
    timing_rows = [[p, t, n, s, round(s / n, 1)] for (p, t), (n, s) in sorted(timing.items())]

    anchoring = Counter()
    with open(FIRST_PASS_CSV, encoding="utf-8") as f:
        first = {int(r["fields_row"]): r for r in csv.DictReader(f)}
    for i, r in enumerate(wb["fields"].iter_rows(min_row=2, values_only=True), start=2):
        if i in first and r[8] in JUDGED and first[i]["verdict"] in JUDGED:
            g = "drawing only" if r[6] in DRAWN else "written"
            anchoring[(g, first[i]["verdict"], r[8])] += 1
    anchoring_rows = [[g, a, b, n] for (g, a, b), n in sorted(anchoring.items())]

    os.makedirs(OUT_DIR, exist_ok=True)
    head = ["n", "correct", "raw_%", "weighted_%", "ci95_low", "ci95_high"]
    tables = {
        "by_field.csv": (["method", "group", "field"] + head, by_field),
        "by_group.csv": (["method", "group"] + head, by_group),
        "sign_level.csv": (["method", "measure"] + head, sign_rows),
        "error_types.csv": (["kind", "method", "value", "count"],
                            [["error_type", m, e, c] for (m, e), c in sorted(errors.items())]
                            + [["catalog_gap", m, f, c] for (m, f), c in sorted(gaps.items())]
                            + [["non_error_verdict", g, v, c] for (v, g), c in sorted(non_error.items())]
                            + [["sign_tag", "all", t, c] for t, c in sorted(tags.items())]),
        "calibration.csv": (["ocr_confidence_bin", "signs", "fields", "wrong_fields", "field_error_%",
                             "whole_sign_correct", "whole_sign_%", "ci95_low", "ci95_high"], calib_rows),
        "prompt_version.csv": (["prompt_version", "signs", "fields", "wrong_fields", "field_error_%",
                                "whole_sign_correct", "whole_sign_%", "ci95_low", "ci95_high"], version_rows),
        "timing.csv": (["phase", "task", "signs", "seconds", "seconds_per_sign"], timing_rows),
        "anchoring.csv": (["group", "excel_first_pass", "blind_dictation", "fields"], anchoring_rows),
    }
    md = ["# Audit results", "", "Generated by `code/analysis/audit_results.py`. Do not edit by hand.", "",
          f"Main sample: 150 signs ({sum(1 for k in main_ids if signs[k]['method'] == 'excel')} judged in Excel, "
          f"{sum(1 for k in main_ids if signs[k]['method'] == 'dictation')} by blind dictation). "
          f"Pearson r between ocr_confidence and per-sign field error rate (dictation signs): {r_conf:.2f}.", ""]
    for name, (header, rows) in tables.items():
        rows = [r for r in rows if not (len(r) > 3 and r[0] == "excel" and r[-6:-5] == [0])]
        with open(os.path.join(OUT_DIR, name), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        md += [f"## {name}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        md += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows] + [""]
    with open(os.path.join(OUT_DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote {len(tables)} tables and summary.md to {OUT_DIR}")


if __name__ == "__main__":
    main()
