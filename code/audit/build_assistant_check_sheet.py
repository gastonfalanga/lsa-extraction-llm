import argparse
import csv
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

WORKBOOK = "work/audit/audit_sheet.xlsx"
TEXT_LOG = "work/audit/text_scoring_log.csv"
OUTPUT = "work/audit/assistant_check.xlsx"
PAIRS = "work/audit/assistant_check_pairs.csv"
SEED, N_SIGNS = 20261116, 30
VERDICTS = ["Correct", "Wrong", "Ambiguous in source", "Source inconsistent", "Not applicable"]

DICTATION = [
    (12, 33, "dictation_D7.md", "## Parte 1"), (34, 41, "dictation_D7.md", "## Parte 2"),
    (42, 51, "dictation_D7.md", "## Parte 3"), (52, 71, "dictation_5-6.md", None),
    (72, 81, "dictation_7.md", None), (82, 102, "dictation_8-9.md", None),
    (103, 122, "dictation_10-11.md", None), (123, 142, "dictation_12-13.md", None),
    (143, 161, "dictation_14-15.md", None),
]

INSTRUCTIONS = [
    "Your own comparison of your dictation with the extracted values",
    "",
    "For each sign, read your dictation excerpt (sheet 'signs'; the full transcript is in work/audit/<file>",
    "if the excerpt is cut wrong) and, in sheet 'fields', give a verdict for every row by comparing what you",
    "dictated with the extracted value. Do not look at the audit sheet or at the page: judge only from your",
    "dictation, as the assistant did. If your dictation does not say anything about a field, use your best",
    "reading of what you said (for example, nothing about movement = no movement).",
    "",
    "Same rules as the audit:",
    "- palm 'backward' = 'inward'; palm 'outward' = 'forward'; 'space in front of torso' = 'in front of chest';",
    "- vibration, rubbing and oscillation do not imply repetition; tapping does;",
    "- a hand touching the palm or back of the other hand is located on that hand;",
    "- an absent final state is correct if nothing changes, wrong if the dictation describes a change;",
    "- 'Not applicable' for fields of a variant, component or hand that does not exist.",
    "",
    "Columns to fill: verdict (dropdown), correct_value (only if Wrong), note (optional).",
]


STOPWORDS = {"la", "el", "los", "las", "de", "del"}
ALIASES_FILE = "work/audit/dictation_aliases.json"
ALIASES = json.load(open(ALIASES_FILE, encoding="utf-8")) if os.path.exists(ALIASES_FILE) else {}


def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def excerpts(signs_rows):
    out = {}
    for first, last, name, part in DICTATION:
        with open(os.path.join("work/audit", name), encoding="utf-8") as f:
            text = f.read()
        if part:
            start = text.index(part)
            nxt = text.find("\n## ", start + 4)
            text = text[start: nxt if nxt > 0 else len(text)]
        low = norm(text)
        rows = [r for r in signs_rows if first <= r[0] <= last]
        pos, starts = 0, []
        for _, gloss in rows:
            keys = []
            for alt in gloss.split("/"):
                words = [w for w in norm(re.sub(r"\(.*?\)", "", alt)).split() if w not in STOPWORDS and len(w) >= 3]
                if words:
                    keys.append(words[0][:5])
            keys += ALIASES.get(gloss, [])
            hits = []
            for k in keys:
                m = re.compile(r"(?<![a-z0-9])" + re.escape(k)).search(low, pos)
                if m:
                    hits.append(m.start())
            i = min(hits) if hits else -1
            starts.append(i)
            if i >= 0:
                pos = i + 1
        for k, (row, gloss) in enumerate(rows):
            s = starts[k]
            if s < 0:
                out[row] = (name, "[excerpt not found: read the full transcript]")
                continue
            later = [x for x in starts[k + 1:] if x > s]
            out[row] = (name, text[s: later[0] if later else len(text)].strip())
    return out


def build(force):
    if os.path.exists(OUTPUT) and not force:
        sys.exit(f"{OUTPUT} exists and may contain your verdicts. Use --force to rebuild it.")
    settled = {}
    with open(TEXT_LOG, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            settled[r["row"]] = r["verdict"] in ("Correct", "Wrong") and not r["reason"].startswith("[manual override]")
    wb = load_workbook(WORKBOOK, read_only=True)
    signs = [(i, r) for i, r in enumerate(wb["signs"].iter_rows(min_row=2, values_only=True), start=2)
             if r[0] == "main"]
    rng = random.Random(SEED)
    chosen = sorted(rng.sample(signs, N_SIGNS), key=lambda x: x[0])
    chosen_ids = {r[1]: (i, r[6]) for i, r in chosen}
    ex = excerpts([(i, r[6]) for i, r in signs])

    out = Workbook()
    ws = out.active
    ws.title = "README"
    for line in INSTRUCTIONS:
        ws.append([line])
    ws.column_dimensions["A"].width = 120
    s_ws = out.create_sheet("signs")
    s_ws.append(["n", "gloss", "dictation_file", "dictation_excerpt"])
    order = {r[1]: n for n, (i, r) in enumerate(chosen, start=1)}
    for n, (i, r) in enumerate(chosen, start=1):
        name, text = ex.get(i, ("?", ""))
        s_ws.append([n, r[6], name, text])
    for col, w in zip("ABCD", (5, 24, 20, 120)):
        s_ws.column_dimensions[col].width = w
    for row in s_ws.iter_rows(min_row=2):
        row[3].alignment = Alignment(wrap_text=True, vertical="top")

    f_ws = out.create_sheet("fields")
    f_ws.append(["n", "gloss", "variant", "component", "hand", "field", "extracted_value",
                 "verdict", "correct_value", "note", "key"])
    count = 0
    for i, r in enumerate(wb["fields"].iter_rows(min_row=2, values_only=True), start=2):
        if r[1] not in chosen_ids or settled.get(str(i)):
            continue
        hand = {"dominant_hand": "dominant", "non_dominant_hand": "non-dominant"}.get(r[5], "")
        f_ws.append([order[r[1]], r[2], r[3], r[4], hand, r[6], r[7], "", "", "", i])
        count += 1
    dv = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
    f_ws.add_data_validation(dv)
    dv.add(f"H2:H{f_ws.max_row}")
    yellow = PatternFill("solid", fgColor="FFF2CC")
    for row in f_ws.iter_rows(min_row=2, min_col=8, max_col=10):
        for cell in row:
            cell.fill = yellow
    for col, w in zip("ABCDEFGHIJK", (5, 22, 8, 10, 13, 22, 40, 18, 25, 30, 7)):
        f_ws.column_dimensions[col].width = w
    f_ws.column_dimensions["K"].hidden = True
    for ws_ in (s_ws, f_ws):
        for cell in ws_[1]:
            cell.font = Font(bold=True)
        ws_.freeze_panes = "A2"
    out.save(OUTPUT)
    found = sum(1 for i, _ in chosen if not ex.get(i, ("", ""))[1].startswith("[excerpt not found"))
    print(f"{N_SIGNS} signs, {count} fields -> {OUTPUT}  (excerpts found for {found}/{N_SIGNS})")


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def score():
    check = load_workbook(OUTPUT, read_only=True)["fields"]
    audit = {i: r for i, r in enumerate(load_workbook(WORKBOOK, read_only=True)["fields"].iter_rows(
        min_row=2, values_only=True), start=2)}
    pairs, binary, missing, added, as_value, rows_out = [], [], 0, [], 0, []
    for r in check.iter_rows(min_row=2, values_only=True):
        if r[10] is None:
            if any(r[5:10]):
                added.append(r)
            continue
        verdict = r[7]
        if not verdict:
            missing += 1
            continue
        if verdict not in VERDICTS:
            verdict, as_value = "Wrong", as_value + 1
        mine = audit[int(r[10])][8]
        pairs.append((verdict, mine))
        rows_out.append([int(r[10]), audit[int(r[10])][6], verdict, mine or ""])
        if verdict in ("Correct", "Wrong") and mine in ("Correct", "Wrong"):
            binary.append((verdict, mine))
    if missing:
        print(f"{missing} rows without a verdict (ignored)")
    if as_value:
        print(f"{as_value} rows with a value typed in the verdict column (read as Wrong)")
    if added:
        print(f"{len(added)} rows added by the auditor (fields outside the sheet, not scored):")
        for r in added:
            print("   ", [x for x in r[:10] if x is not None])
    with open(PAIRS, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fields_row", "field", "auditor_verdict", "assistant_verdict"])
        w.writerows(rows_out)
    po, k = kappa(pairs)
    print(f"all verdict categories: n={len(pairs)}, agreement={po:.3f}, Cohen's kappa={k:.3f}")
    po, k = kappa(binary)
    print(f"Correct/Wrong only:     n={len(binary)}, agreement={po:.3f}, Cohen's kappa={k:.3f}")
    print("disagreements (auditor -> assistant):", Counter((a, b) for a, b in pairs if a != b).most_common())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    score() if a.score else build(a.force)
