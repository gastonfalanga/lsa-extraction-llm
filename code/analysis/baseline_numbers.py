import glob
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict

RAW_DIR = "work/outputs/raw_ocr_history/first_commit"
PER_BATCH_CSV = "work/raw_ocr_history/per_batch.csv"
PROMPT = "prompts/scan_pdf.md"
EXCLUDED = {"lote_156.json"}
DRAWN = ("initial_position", "initial_orientation", "final_position", "final_orientation")


def load():
    signs, raw_text = [], {}
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "lote_*.json"))):
        name = os.path.basename(path)
        if name in EXCLUDED:
            continue
        with open(path, encoding="utf-8") as f:
            raw_text[name] = f.read()
        for s in json.loads(raw_text[name]):
            s["_batch"] = name
            signs.append(s)
    return signs, raw_text


def pearson(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


def main():
    signs, raw_text = load()
    out = []

    def row(label, value, draft):
        out.append((label, value, draft))

    batches = {s["_batch"] for s in signs}
    pages = {(s["ocr_data"]["source_batch_file"], s["ocr_data"].get("source_page_ocr")) for s in signs}
    row("signs", len(signs), "1,674")
    row("batches", len(batches), "155")
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    pdf_pages = sum(len(fitz.open(p)) for p in glob.glob("data/raw/v1_lote_*.pdf"))
    row("PDF pages in the batch files", pdf_pages, "595")
    row("mean pages per batch", round(pdf_pages / len(batches), 1), "3.8")

    conf = [s["ocr_data"]["ocr_confidence"] for s in signs]
    srt = sorted(conf)
    row("ocr_confidence mean", round(sum(conf) / len(conf), 2), "0.75")
    row("ocr_confidence median", srt[len(srt) // 2], "0.80")
    row("signs below 0.75", sum(1 for c in conf if c < 0.75), "607")
    row("distinct confidence values", len(set(conf)), "14")
    row("share at 0.80 (%)", round(100 * sum(1 for c in conf if c == 0.8) / len(conf)), "36")
    tc = [s["ocr_data"].get("translation_confidence") for s in signs]
    row("translation_confidence = 0.95 (%)", round(100 * sum(1 for c in tc if c == 0.95) / len(tc)), "83")
    n_inferred = [len(s["ocr_data"].get("visually_deduced_fields") or []) for s in signs]
    row("r(confidence, n inferred fields)", round(pearson(conf, n_inferred), 2), "-0.08")

    present, logged, other = Counter(), Counter(), Counter()
    for s in signs:
        vdf = set(s["ocr_data"].get("visually_deduced_fields") or [])
        for p in vdf:
            other[p.rsplit(".", 1)[-1]] += 1
        for vi, v in enumerate(s.get("sign_variants", [])):
            for ci, c in enumerate(v.get("sequential_components", [])):
                for h in ("dominant_hand", "non_dominant_hand"):
                    if not c.get(h):
                        continue
                    for fld in DRAWN:
                        if fld in c[h]:
                            present[fld] += 1
                            if f"sign_variants[{vi}].sequential_components[{ci}].{h}.{fld}" in vdf:
                                logged[fld] += 1
    row("hands with initial position", present["initial_position"], "3,145")
    row("initial position logged as inferred", logged["initial_position"], "3,086")
    row("final states present", present["final_position"], "436")
    row("logged final position / orientation", f'{logged["final_position"]} / {logged["final_orientation"]}', "407 / 403")
    row("inferred final position / orientation (all paths)", f'{other["final_position"]} / {other["final_orientation"]}', "417 / 412")
    row("inferred path / initial handshape", f'{other["path"]} / {other["initial_configuration"]}', "161 / 26")

    nmc = sum(1 for s in signs for v in s.get("sign_variants", []) for c in v.get("sequential_components", [])
              if (c.get("non_manual_components") or {}).get("nmc_text"))
    row("components with nmc_text", nmc, "28")

    esc_batches, esc_signs = set(), 0
    for name, text in raw_text.items():
        for s in json.loads(text):
            if '\\"' in json.dumps(s, ensure_ascii=False):
                esc_signs += 1
                esc_batches.add(name)
    row("signs / batches with escaped quotes", f"{esc_signs} / {len(esc_batches)}", "67 / 34")
    notes = sum(1 for s in signs if s.get("human_notes"))
    row("signs with reviewer notes in the last scan", notes, "0")
    invented = sum(len(re.findall(r"\b(O\.P\.|O\.A\.|L\.C\.|L\.E\.)", json.dumps(s, ensure_ascii=False))) for s in signs)
    row("mentions of invented codes (O.P., O.A., L.C., L.E.)", invented, "3")
    second_hand = sum(1 for s in signs if re.search(r"second hand", s["ocr_data"].get("ocr_notes", ""), re.I))
    row("signs whose notes mention a \"second hand\"", second_hand, "39")

    with open(PER_BATCH_CSV, encoding="utf-8-sig") as f:
        import csv
        dates = [r["first_date"] for r in csv.DictReader(f) if r["batch"] not in EXCLUDED]
    by_day = Counter(dates)
    row("commit days / max batches in a day", f"{len(by_day)} / {max(by_day.values())}", "16 / 30")
    row("first / last scan commit", f"{min(dates)} / {max(dates)}", "2026-08-28 / 2026-09-15")
    log = subprocess.run(["git", "log", "--follow", "--format=%ad", "--date=short", "--", PROMPT],
                         capture_output=True, text=True, check=True).stdout.split()
    in_run = [d for d in log if "2026-08-22" <= d <= "2026-09-16"]
    row("prompt revisions 08-22 to 09-16", len(in_run), "37")

    width = max(len(r[0]) for r in out)
    for label, value, draft in out:
        same = str(value).replace(",", "") == draft.replace(",", "")
        try:
            same = same or float(value) == float(draft)
        except (TypeError, ValueError):
            pass
        flag = "" if same else "   <-- check"
        print(f"{label:<{width}}  {str(value):>22}   draft: {draft}{flag}")
    print("\nNot recomputed here: 27 signs that differ from the backup copy (needs the backup); schema conformance, missing pages and text layer "
          "(own scripts: schema_conformance.py and text_layer.py).")


if __name__ == "__main__":
    main()
