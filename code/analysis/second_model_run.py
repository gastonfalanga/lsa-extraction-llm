import argparse
import concurrent.futures as cf
import csv
import glob
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict

import fitz
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(__file__))
from build_audit_pack import load_pdf_page_indexes, load_raw_signs, pdf_page_index
from build_audit_sheet import HAND_FIELDS, get_path, render

MODEL = "claude-opus-5-5"
PROMPT_COMMIT, PROMPT_PATH = "9c9acb7", "ocr/prompt_ocr.md"
WORK = os.environ.get("SECOND_MODEL_WORKDIR",
                      "/private/tmp/claude-502/-Users-gaston-falanga-LSA-MorphDict/"
                      "4b330f29-8586-4cd3-89ef-13f9ab2bda1d/scratchpad/extraction_run")
OUT = "work/second_model"
SAMPLE = "work/audit/audit_sample.csv"
WORKBOOK = "work/audit/audit_sheet.xlsx"
CLI = os.environ.get("CLAUDE_CLI", glob.glob(os.path.expanduser(
    "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"))[-1])
JUDGED = {"Correct", "Wrong"}
ABSENT = "(absent)"

INSTRUCTION = """You are given two files in the current folder: prompt.md and page.pdf.
Use no other context: ignore anything you may know or remember about any project, dataset or earlier conversation,
and do not read any file other than these two.
Read prompt.md and follow it to extract every dictionary entry on the single page in page.pdf.
For the ids, start with lsa_0001. Reply with the JSON array only, with no other text."""


def norm_text(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def targets(limit=None):
    sample = list(csv.DictReader(open(SAMPLE, encoding="utf-8-sig")))
    main = [r for r in sample if r["set"] == "main"]
    return main[:limit] if limit else main


def page_key(batch, index):
    return f"{os.path.splitext(batch)[0]}_p{index + 1}"


def prepare(limit):
    raw, _ = load_raw_signs()
    stored = load_pdf_page_indexes()
    prompt = subprocess.run(["git", "show", f"{PROMPT_COMMIT}:{PROMPT_PATH}"], capture_output=True, text=True,
                            check=True).stdout
    index = []
    for r in targets(limit):
        sign = raw[r["ocr_id"]]
        batch = sign["ocr_data"]["source_batch_file"]
        pi = pdf_page_index(sign, r["id"], stored, raw)
        key = page_key(batch, pi)
        folder = os.path.join(WORK, key)
        if not os.path.exists(os.path.join(folder, "page.pdf")):
            os.makedirs(folder, exist_ok=True)
            with fitz.open(os.path.join("data/raw", batch)) as doc:
                one = fitz.open()
                one.insert_pdf(doc, from_page=pi, to_page=pi)
                one.save(os.path.join(folder, "page.pdf"))
            with open(os.path.join(folder, "prompt.md"), "w", encoding="utf-8") as f:
                f.write(prompt)
        index.append({"ocr_id": r["ocr_id"], "page": key, "slot": r["sign_index_on_page"]})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "targets.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)
    print(f"{len(index)} signs on {len({t['page'] for t in index})} pages -> {WORK}")


def run_page(key):
    folder = os.path.join(WORK, key)
    dest = os.path.join(OUT, "raw", key + ".json")
    if os.path.exists(dest) and parse_output(key) is not None:
        return key, "cached"
    cmd = [CLI, "-p", INSTRUCTION, "--model", MODEL, "--tools", "Read",
           "--allowedTools", f"Read({folder}/**)", "--permission-mode", "dontAsk",
           "--no-session-persistence", "--output-format", "json"]
    r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=1800)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(r.stdout if r.returncode == 0 else json.dumps({"error": r.stderr[-3000:], "stdout": r.stdout[-3000:]}))
    return key, "ok" if r.returncode == 0 else "error"


def run(limit, jobs):
    t = json.load(open(os.path.join(OUT, "targets.json"), encoding="utf-8"))
    pages = sorted({x["page"] for x in t})[: (limit or None)]
    pending = [p for p in pages if parse_output(p) is None]
    print(f"{len(pages) - len(pending)} done, {len(pending)} pending", flush=True)
    failed = False
    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = {}
        for key in pending:
            if failed:
                break
            futures[ex.submit(run_page, key)] = key
            while len(futures) >= jobs and not failed:
                done, _ = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
                for f in done:
                    key, status = f.result()
                    print(key, status, flush=True)
                    failed = failed or status == "error"
                    del futures[f]
        for f in cf.as_completed(futures):
            key, status = f.result()
            print(key, status, flush=True)
            failed = failed or status == "error"
    left = sum(1 for p in pages if parse_output(p) is None)
    print(f"stopped: a call failed (usage limit?); {left} pages pending" if failed else f"finished; {left} pending",
          flush=True)
    sys.exit(1 if left else 0)


def parse_output(key):
    path = os.path.join(OUT, "raw", key + ".json")
    if not os.path.exists(path):
        return None
    try:
        wrapper = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    text = wrapper.get("result", "") if isinstance(wrapper, dict) else ""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


PALM_EQ = {"palm outward": "palm forward", "palm backward": "palm inward"}


def canon(field, value):
    v = norm_text(value)
    if v in ("", "(absent)", "none", "null"):
        return ""
    if field.endswith("orientation"):
        m = re.search(r"palm [a-z ]+?(?= \||$)", v)
        p = m.group(0).strip() if m else v
        return PALM_EQ.get(p, p)
    if field.endswith("position"):
        v = re.sub(r"^(body|space): ", "", v).replace("space in front of torso", "space in front of chest")
        return v
    if field in ("movement_contact", "movement_repetition"):
        return "true" if v == "true" else ""
    if field == "non_manual_components":
        parts = [x.strip() for x in re.split(r"[|;]", v) if x.strip() and not x.strip().startswith("nmc_text")]
        return ";".join(sorted(parts))
    if field in ("movement_manner", "movement_path"):
        return ";".join(sorted(x.strip() for x in v.split(";") if x.strip()))
    return v


def hand_values(entry):
    out = {}
    for vi, v in enumerate(entry.get("sign_variants", []), start=1):
        for c in v.get("sequential_components", []):
            for h in ("dominant_hand", "non_dominant_hand"):
                hand = c.get(h)
                if not hand:
                    continue
                out[(vi, int(c.get("component_order", 1)), h)] = {f: render(get_path(hand, p)) for f, p in HAND_FIELDS}
            out[(vi, int(c.get("component_order", 1)), "nmc")] = {
                "non_manual_components": render(c.get("non_manual_components"))}
    return out


def score():
    t = json.load(open(os.path.join(OUT, "targets.json"), encoding="utf-8"))
    wb = load_workbook(WORKBOOK, read_only=True)
    signs = {r[1]: r for r in wb["signs"].iter_rows(min_row=2, values_only=True) if r[0] == "main"}
    rows = [r for r in wb["fields"].iter_rows(min_row=2, values_only=True) if r[1] in signs]
    sample = {r["ocr_id"]: r for r in csv.DictReader(open(SAMPLE, encoding="utf-8-sig"))}
    variant_no = defaultdict(dict)
    for r in rows:
        labels = variant_no[r[1]]
        if r[3] not in labels:
            labels[r[3]] = len(labels) + 1
    results, missing = [], []
    for x in t:
        entries = parse_output(x["page"])
        sign = signs.get(x["ocr_id"])
        if entries is None or sign is None:
            missing.append((x["ocr_id"], "no output"))
            continue
        gloss = norm_text(sign[6]).split("/")[0].strip()
        slot = int(x["slot"])
        entry = entries[slot - 1] if 0 < slot <= len(entries) else None
        if entry is None or gloss[:5] not in norm_text(entry.get("spanish_word", "")):
            match = [e for e in entries if gloss[:5] and gloss[:5] in norm_text(e.get("spanish_word", ""))]
            entry = match[0] if match else None
        if entry is None:
            missing.append((x["ocr_id"], "entry not found"))
            continue
        vals = hand_values(entry)
        for r in rows:
            if r[1] != x["ocr_id"] or r[8] not in JUDGED:
                continue
            ref = r[7] if r[8] == "Correct" else r[9]
            if ref in (None, ""):
                continue
            field = r[6]
            hand = "nmc" if field == "non_manual_components" else (r[5] or "")
            key = (variant_no[r[1]][r[3]], int(r[4] or 1), hand)
            mine_hand = vals.get(key, {})
            mine = mine_hand.get(field, ABSENT)
            if field in ("final_position", "final_orientation"):
                mine_init = mine_hand.get(field.replace("final", "initial"), ABSENT)
                mine_changes = mine != ABSENT and canon(field, mine) != canon(field, mine_init)
                if ref == ABSENT:
                    second_ok = not mine_changes
                else:
                    second_ok = canon(field, mine if mine_changes else mine_init) == canon(field, ref)
            else:
                second_ok = canon(field, mine) == canon(field, ref)
            results.append({"ocr_id": r[1], "weight": float(sample[r[1]]["weight"]), "field": field,
                            "printed": r[10], "reference_absent": ref == ABSENT,
                            "gemini": r[8] == "Correct",
                            "second": second_ok})
    with open(os.path.join(OUT, "scores.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    def acc(items, key):
        sw = sum(i["weight"] for i in items)
        return 100 * sum(i["weight"] for i in items if i[key]) / sw if sw else float("nan")
    groups = {
        "printed in the text": [i for i in results if i["printed"] == "Yes"],
        "only in the drawing": [i for i in results if i["printed"] != "Yes" and not i["reference_absent"]],
        "nothing to extract": [i for i in results if i["printed"] != "Yes" and i["reference_absent"]],
        "initial position": [i for i in results if i["field"] == "initial_position"],
        "initial orientation": [i for i in results if i["field"] == "initial_orientation"],
        "all fields": results,
    }
    lines = ["# Second model (Claude Opus 5.5) on the audited signs", "",
             f"Signs scored: {len({i['ocr_id'] for i in results})} of {len(t)}; not scored: {len(missing)} "
             f"{missing[:10]}", "", "| Group | fields | Gemini % (weighted) | Opus % (weighted) |", "|---|---|---|---|"]
    for g, items in groups.items():
        lines.append(f"| {g} | {len(items)} | {acc(items, 'gemini'):.1f} | {acc(items, 'second'):.1f} |")
    lines += ["", "Overlap on values only the drawing gives (unweighted fields):", ""]
    d = groups["only in the drawing"]
    both = sum(1 for i in d if i["gemini"] and i["second"])
    none_ = sum(1 for i in d if not i["gemini"] and not i["second"])
    g_only = sum(1 for i in d if i["gemini"] and not i["second"])
    s_only = sum(1 for i in d if not i["gemini"] and i["second"])
    lines += [f"- both right {both}, both wrong {none_}, only Gemini right {g_only}, only Opus right {s_only} "
              f"(of {len(d)}).",
              f"- Of the fields Gemini got wrong, Opus also got {100 * none_ / max(none_ + s_only, 1):.0f}% wrong."]
    for f in ("final_position", "final_orientation"):
        ch = [i for i in results if i["field"] == f and not i["reference_absent"]]
        lines.append(f"- {f} with a real change: Gemini {acc(ch, 'gemini'):.1f}%, Opus {acc(ch, 'second'):.1f}% "
                     f"({len(ch)} fields).")
    with open(os.path.join(OUT, "results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["prepare", "run", "score"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    {"prepare": lambda: prepare(a.limit), "run": lambda: run(a.limit, a.jobs), "score": score}[a.stage]()
