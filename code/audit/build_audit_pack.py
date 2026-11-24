import argparse
import glob
import html
import json
import os
from collections import defaultdict

import fitz
from openpyxl import load_workbook
from PIL import Image

AUDIT_SHEET = "work/audit/audit_sheet.xlsx"
RAW_DIR = "work/outputs/raw_ocr_history/first_commit"
DATASET_GLOB = "data/dataset/cat_*.json"
PDF_DIR = "data/raw"
OUTPUT_DIR = "work/outputs/audit_pack"
ZOOM = 2.0
JPEG_QUALITY = 75


EXCLUDED_FILES = {"lote_156.json"}


def load_raw_signs():
    signs, slots = {}, defaultdict(int)
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "lote_*.json"))):
        if os.path.basename(path) in EXCLUDED_FILES:
            continue
        with open(path, encoding="utf-8") as f:
            for sign in json.load(f):
                signs[sign["sign_id"]] = sign
                ocr = sign.get("ocr_data", {})
                slots[(ocr.get("source_batch_file"), ocr.get("source_page_ocr"))] += 1
    return signs, slots


def load_pdf_page_indexes():
    indexes = {}
    for path in glob.glob(DATASET_GLOB):
        with open(path, encoding="utf-8") as f:
            for sign in json.load(f)["signs"]:
                index = (sign.get("ocr_data") or {}).get("source_pdf_page_index")
                if index:
                    indexes[sign["id"]] = index
    return indexes


def pdf_page_index(sign, hex_id, stored, raw_signs):
    if hex_id in stored:
        return stored[hex_id] - 1
    ocr = sign["ocr_data"]
    pages = sorted({s["ocr_data"].get("source_page_ocr") for s in raw_signs.values()
                    if s["ocr_data"].get("source_batch_file") == ocr["source_batch_file"]
                    and s["ocr_data"].get("source_page_ocr") is not None})
    return pages.index(ocr["source_page_ocr"])


def render_page(batch_file, page_index, cache):
    key = (batch_file, page_index)
    if key not in cache:
        name = f"{os.path.splitext(batch_file)[0]}_p{page_index + 1}.jpg"
        with fitz.open(os.path.join(PDF_DIR, batch_file)) as doc:
            pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        img.save(os.path.join(OUTPUT_DIR, name), quality=JPEG_QUALITY)
        cache[key] = name
    return cache[key]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blind", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    help="signs sheet rows to show with the page only: no extracted values, no verdicts")
    args = ap.parse_args()

    wb = load_workbook(AUDIT_SHEET, read_only=True)
    signs_rows = list(wb["signs"].iter_rows(values_only=True))
    header = signs_rows[0]
    col = {name: i for i, name in enumerate(header)}

    fields_by_sign = defaultdict(list)
    for row_number, row in enumerate(wb["fields"].iter_rows(min_row=2, values_only=True), start=2):
        fields_by_sign[row[1]].append((row_number, row))

    raw_signs, slots = load_raw_signs()
    stored = load_pdf_page_indexes()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cache = {}

    sections, nav = [], []
    for sheet_row, row in enumerate(signs_rows[1:], start=2):
        if args.blind and not args.blind[0] <= sheet_row <= args.blind[1]:
            continue
        ocr_id, hex_id = row[col["ocr_id"]], row[col["id"]]
        sign = raw_signs[ocr_id]
        ocr = sign["ocr_data"]
        page_index = pdf_page_index(sign, hex_id, stored, raw_signs)
        image = render_page(ocr["source_batch_file"], page_index, cache)

        total = max(slots[(ocr["source_batch_file"], ocr["source_page_ocr"])], 1)
        slot = int(ocr["sign_index_on_page"])
        top, height = (slot - 1) / total * 100, 100 / total

        table = "".join(
            f"<tr><td class='row'>{n}</td><td>{html.escape(str(r[3]))}</td><td>{r[4]}</td>"
            f"<td>{html.escape(r[5] or '')}</td><td>{html.escape(r[6])}</td>"
            f"<td class='{'absent' if r[7] == '(absent)' else ''}'>{html.escape(str(r[7]))}</td>"
            f"<td>{html.escape(str(r[10] or ''))}</td></tr>"
            for n, r in fields_by_sign[ocr_id])
        sign_level = "".join(
            f"<li>{name}: <b>{html.escape(str(row[col[name + '_extracted']]))}</b></li>"
            for name in ("gloss", "hand_count", "variant_count", "component_counts"))

        if args.blind:
            sections.append(f"""
<section id="s{sheet_row}">
  <h2>{sheet_row}. {html.escape(str(row[col['gloss_extracted']]))}</h2>
  <div class="page blind"><img src="{image}" loading="lazy">
    <div class="slot" style="top:{top:.1f}%;height:{height:.1f}%"></div></div>
</section>""")
            continue

        anchor = f"s{sheet_row}"
        nav.append(f"<a href='#{anchor}'>{row[col['set']][0].upper()} {html.escape(str(row[col['gloss_extracted']]))}</a>")
        sections.append(f"""
<section id="{anchor}">
  <h2>{html.escape(str(row[col['gloss_extracted']]))}
    <small>{row[col['set']]} · {ocr_id} · {hex_id} · {ocr['source_batch_file']} · printed page {ocr['source_page_ocr']} · slot {slot}/{total} · signs sheet row {sheet_row}</small></h2>
  <div class="grid">
    <div class="page"><img src="{image}" loading="lazy">
      <div class="slot" style="top:{top:.1f}%;height:{height:.1f}%"></div></div>
    <div><ul>{sign_level}</ul>
      <table><tr><th>fields row</th><th>variant</th><th>comp.</th><th>hand</th><th>field</th><th>extracted</th><th>printed?</th></tr>{table}</table>
    </div>
  </div>
</section>""")

    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Audit pack</title>
<style>
body{{font:14px system-ui,sans-serif;margin:0;background:#fff;color:#111}}
nav{{position:sticky;top:0;background:#f3f3f3;padding:6px;font-size:12px;max-height:20vh;overflow:auto;z-index:2}}
nav a{{margin-right:8px;white-space:nowrap}}
section{{padding:12px 16px;border-top:3px solid #333}}
h2 small{{font-weight:normal;font-size:12px;color:#555;display:block}}
.grid{{display:grid;grid-template-columns:minmax(0,55%) minmax(0,45%);gap:16px;align-items:start}}
.page.blind{{max-width:900px}}
.page{{position:relative}} .page img{{width:100%;display:block;border:1px solid #ccc}}
.slot{{position:absolute;left:0;right:0;border:3px solid #d00;box-sizing:border-box;pointer-events:none}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border:1px solid #ddd;padding:2px 4px;text-align:left}}
td.row{{color:#555}} td.absent{{color:#999}}
</style></head><body>
<nav>{''.join(nav)}</nav>
{''.join(sections)}
</body></html>"""
    name = "blind.html" if args.blind else "index.html"
    with open(os.path.join(OUTPUT_DIR, name), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"{len(sections)} signs, {len(cache)} pages -> {OUTPUT_DIR}/{name}")


if __name__ == "__main__":
    main()
