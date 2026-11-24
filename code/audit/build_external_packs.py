import argparse
import csv
import html
import json
import os
import random
import shutil
import subprocess
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(__file__))
import build_audit_pack as pack

AUDIT_SHEET = "work/audit/audit_sheet.xlsx"
SAMPLE_CSV = "work/audit/audit_sample.csv"
EXTRACTION_SCHEMA_COMMIT = "9c9acb7"
DRAWN = ("initial_position", "initial_orientation", "final_position", "final_orientation")
BAD_PAGE_BATCHES = {"v1_lote_011.pdf", "v1_lote_012.pdf", "v1_lote_017.pdf", "v1_lote_043.pdf", "v1_lote_061.pdf",
                    "v1_lote_066.pdf", "v1_lote_074.pdf", "v1_lote_103.pdf", "v1_lote_120.pdf", "v1_lote_129.pdf",
                    "v1_lote_111_adjust_set.pdf"}
YELLOW = PatternFill("solid", fgColor="FFF2CC")


def catalogs():
    schema = json.loads(subprocess.run(["git", "show", f"{EXTRACTION_SCHEMA_COMMIT}:schema.json"],
                                       capture_output=True, text=True, check=True).stdout)
    d = schema["definitions"]
    clean = lambda key: [v for v in d[key]["enum"] if v != "dummy"]
    return {
        "position": ["body: " + v for v in clean("body_location_enum")] + ["space: " + v for v in clean("space_location_enum")],
        "palm": clean("hand_orientation_enum"),
        "arm": clean("arm_orientation_enum"),
        "handshape": clean("handshape_enum"),
        "manner": clean("hand_movement_manner_enum"),
        "path": clean("hand_movement_path_enum"),
        "nmc": clean("nmc_facial_enum") + clean("nmc_body_movement_enum"),
    }


def add_lists(wb, cats):
    ws = wb.create_sheet("listas")
    refs = {}
    for c, (name, values) in enumerate(cats.items(), start=1):
        ws.cell(row=1, column=c, value=name)
        for r, v in enumerate(values, start=2):
            ws.cell(row=r, column=c, value=v)
        letter = ws.cell(row=1, column=c).column_letter
        refs[name] = f"listas!${letter}$2:${letter}${len(values) + 1}"
    ws.sheet_state = "hidden"
    return refs


def dropdown(ws, ref_or_values, col, n_rows):
    formula = ref_or_values if isinstance(ref_or_values, str) else '"' + ",".join(ref_or_values) + '"'
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{col}2:{col}{max(n_rows, 2)}")


def style(ws, widths, fill_from=None):
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    if fill_from:
        for row in ws.iter_rows(min_row=2, min_col=fill_from[0], max_col=fill_from[1]):
            for cell in row:
                cell.fill = YELLOW


def write_pages(out_dir, items):
    raw, slots = pack.load_raw_signs()
    stored = pack.load_pdf_page_indexes()
    pack.OUTPUT_DIR = out_dir
    cache, sections = {}, []
    for n, label, sign, hex_id in items:
        ocr = sign["ocr_data"]
        image = pack.render_page(ocr["source_batch_file"].replace("_adjust_set", ""),
                                 pack.pdf_page_index(sign, hex_id, stored, raw), cache)
        total = max(slots[(ocr["source_batch_file"], ocr["source_page_ocr"])], 1)
        slot = int(ocr["sign_index_on_page"])
        top, height = (slot - 1) / total * 100, 100 / total
        sections.append(f"""
<section id="n{n}"><h2>{n}. {html.escape(label)}</h2>
  <div class="page"><img src="{image}" loading="lazy">
    <div class="slot" style="top:{top:.1f}%;height:{height:.1f}%"></div></div></section>""")
    nav = "".join(f"<a href='#n{n}'>{n}</a>" for n, *_ in items)
    with open(os.path.join(out_dir, "pages.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html><html><head><meta charset="utf-8"><title>Páginas</title><style>
body{{font:15px system-ui,sans-serif;margin:0;color:#111;background:#fff}}
nav{{position:sticky;top:0;background:#f3f3f3;padding:6px;z-index:2}} nav a{{margin-right:8px}}
section{{padding:12px 16px;border-top:3px solid #333}} .page{{position:relative;max-width:900px}}
.page img{{width:100%;display:block;border:1px solid #ccc}}
.slot{{position:absolute;left:0;right:0;border:3px solid #d00;box-sizing:border-box;pointer-events:none}}
</style></head><body><nav>{nav}</nav>{''.join(sections)}</body></html>""")
    return raw


def prepare(out_dir, force):
    if os.path.exists(out_dir):
        if not force:
            sys.exit(f"{out_dir} exists. Use --force to rebuild it (the sheet inside may already be filled in).")
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)


def second_auditor(force, n_signs=56, seed=20261116):
    base = "work/second_auditor"
    out = os.path.join(base, "to_send")
    prepare(out, force)
    cats = catalogs()
    with open(SAMPLE_CSV, encoding="utf-8-sig") as f:
        sample = {r["ocr_id"]: r for r in csv.DictReader(f) if r["set"] == "main"}
    rng = random.Random(seed)
    chosen = rng.sample(sorted(sample), n_signs)
    arms = ["describe"] * (n_signs // 2) + ["verify"] * (n_signs - n_signs // 2)
    rng.shuffle(arms)
    rng.shuffle(chosen)
    order = list(zip(range(1, n_signs + 1), chosen, arms))

    audit = load_workbook(AUDIT_SHEET, read_only=True)
    fields = {}
    for i, r in enumerate(audit["fields"].iter_rows(min_row=2, values_only=True), start=2):
        if r[1] in sample and r[6] in DRAWN:
            fields.setdefault(r[1], []).append((i, r))
    gloss = {r[1]: r[6] for r in audit["signs"].iter_rows(min_row=2, values_only=True)}

    raw_signs = pack.load_raw_signs()[0]
    write_pages(out, [(n, gloss[o], raw_signs[o], sample[o]["id"]) for n, o, _ in order])

    wb = Workbook()
    ws = wb.active
    ws.title = "orden"
    ws.append(["n", "seña", "formato", "hecho (sí)"])
    for n, o, arm in order:
        ws.append([n, gloss[o], "describir" if arm == "describe" else "verificar", ""])
    ws.append([])
    ws.append(["sesión", "fecha", "hora de inicio", "hora de fin"])
    for s in range(1, 5):
        ws.append([s, "", "", ""])
    style(ws, {"A": 8, "B": 26, "C": 12, "D": 12})

    refs = add_lists(wb, {**cats, "final_position": ["(sin cambio)"] + cats["position"],
                          "final_palm": ["(sin cambio)"] + cats["palm"]})
    d = wb.create_sheet("describir", 1)
    d.append(["n", "seña", "variante", "componente", "mano", "en_el_dibujo", "posicion_inicial",
              "orientacion_inicial", "brazo_inicial", "posicion_final", "orientacion_final", "nota", "key"])
    v = wb.create_sheet("verificar", 2)
    v.append(["n", "seña", "variante", "componente", "mano", "campo", "valor", "veredicto", "valor_correcto",
              "nota", "key"])
    key_rows = []
    for n, o, arm in order:
        key_rows.append([n, o, sample[o]["id"], arm])
        rows = fields[o]
        if arm == "describe":
            slots_seen = []
            for i, r in rows:
                slot = (r[3], r[4], r[5])
                if slot not in slots_seen:
                    slots_seen.append(slot)
            for variant, comp, hand in slots_seen:
                keys = ";".join(str(i) for i, r in rows if (r[3], r[4], r[5]) == (variant, comp, hand))
                label = {"dominant_hand": "dominante", "non_dominant_hand": "no dominante"}.get(hand, hand)
                d.append([n, gloss[o], variant, comp, label, "", "", "", "", "", "", "", keys])
        else:
            for i, r in rows:
                label = {"dominant_hand": "dominante", "non_dominant_hand": "no dominante"}.get(r[5], r[5])
                campo = {"initial_position": "posición inicial", "initial_orientation": "orientación inicial",
                         "final_position": "posición final", "final_orientation": "orientación final"}[r[6]]
                v.append([n, gloss[o], r[3], r[4], label, campo, r[7], "", "", "", i])
    dropdown(d, ["sí", "no"], "F", d.max_row)
    dropdown(d, refs["position"], "G", d.max_row)
    dropdown(d, refs["palm"], "H", d.max_row)
    dropdown(d, refs["arm"], "I", d.max_row)
    dropdown(d, refs["final_position"], "J", d.max_row)
    dropdown(d, refs["final_palm"], "K", d.max_row)
    dropdown(v, ["Correct", "Wrong", "Ambiguous in source", "Not applicable"], "H", v.max_row)
    style(d, {"A": 5, "B": 22, "C": 9, "D": 11, "E": 13, "F": 12, "G": 34, "H": 26, "I": 18, "J": 34,
              "K": 26, "L": 30, "M": 6}, fill_from=(6, 12))
    style(v, {"A": 5, "B": 22, "C": 9, "D": 11, "E": 13, "F": 18, "G": 44, "H": 18, "I": 30, "J": 30, "K": 6},
          fill_from=(8, 10))
    d.column_dimensions["M"].hidden = True
    v.column_dimensions["K"].hidden = True
    wb.save(os.path.join(out, "planilla.xlsx"))
    shutil.copyfile(os.path.join(base, "guia.md"), os.path.join(out, "guia.md"))
    with open(os.path.join(base, "key.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "ocr_id", "id", "arm"])
        w.writerows(key_rows)
    print(f"{n_signs} signs ({arms.count('describe')} describe, {arms.count('verify')} verify), "
          f"{d.max_row - 1} describe rows, {v.max_row - 1} verify rows -> {out}; key -> {base}/key.csv")


def from_scratch(force, n_signs=20, seed=20261117):
    base = "work/annotation"
    out = os.path.join(base, "to_send")
    prepare(out, force)
    cats = catalogs()
    with open(SAMPLE_CSV, encoding="utf-8-sig") as f:
        sampled = {r["ocr_id"] for r in csv.DictReader(f)}
    raw, _ = pack.load_raw_signs()
    pool = sorted(k for k, s in raw.items() if k not in sampled
                  and s["ocr_data"]["source_batch_file"] not in BAD_PAGE_BATCHES)
    chosen = random.Random(seed).sample(pool, n_signs)
    write_pages(out, [(n, raw[o]["spanish_word"], raw[o], None) for n, o in enumerate(chosen, start=1)])

    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    for line in [
        "Annotate each sign from scratch, from the page only (pages.html), without looking at the dataset,",
        "the viewer or the extraction. Fill one row per variant, component and hand; leave unused rows empty and",
        "add rows if a sign needs more. Values come from the extraction-time catalogs (dropdowns).",
        "Time: write the start and end time of every session in the 'timing' sheet; pauses do not count.",
        "Movement: manner_1/manner_2 and path_1/path_2 hold up to two values each.",
    ]:
        ws.append([line])
    ws.column_dimensions["A"].width = 110
    t = wb.create_sheet("timing")
    t.append(["session", "date", "start (hh:mm)", "end (hh:mm)", "signs done (n from-to)"])
    for s in range(1, 5):
        t.append([s, "", "", "", ""])
    style(t, {"A": 9, "B": 12, "C": 14, "D": 14, "E": 22})
    refs = add_lists(wb, {**cats, "final_position": ["(no change)"] + cats["position"],
                          "final_palm": ["(no change)"] + cats["palm"],
                          "final_handshape": ["(no change)"] + cats["handshape"]})
    a = wb.create_sheet("annotation", 1)
    header = ["n", "gloss", "variant", "component", "hand", "initial_handshape", "initial_position", "initial_palm",
              "initial_arm", "manner_1", "manner_2", "path_1", "path_2", "contact", "repetition",
              "final_handshape", "final_position", "final_palm", "non_manual_1", "non_manual_2", "note"]
    a.append(header)
    for n, o in enumerate(chosen, start=1):
        for variant, comp, hand in (("A", 1, "dominant"), ("A", 1, "non-dominant"),
                                    ("A", 2, "dominant"), ("A", 2, "non-dominant")):
            a.append([n, raw[o]["spanish_word"], variant, comp, hand] + [""] * (len(header) - 5))
    rows = a.max_row + 40
    for col, ref in (("F", refs["handshape"]), ("G", refs["position"]), ("H", refs["palm"]), ("I", refs["arm"]),
                     ("J", refs["manner"]), ("K", refs["manner"]), ("L", refs["path"]), ("M", refs["path"]),
                     ("P", refs["final_handshape"]), ("Q", refs["final_position"]), ("R", refs["final_palm"]),
                     ("S", refs["nmc"]), ("T", refs["nmc"])):
        dropdown(a, ref, col, rows)
    dropdown(a, ["yes", "no"], "N", rows)
    dropdown(a, ["yes", "no"], "O", rows)
    style(a, {"A": 5, "B": 20, "C": 8, "D": 10, "E": 13, "F": 16, "G": 30, "H": 22, "I": 16, "J": 14, "K": 14,
              "L": 14, "M": 14, "N": 9, "O": 10, "P": 16, "Q": 30, "R": 22, "S": 18, "T": 18, "U": 30},
          fill_from=(3, 21))
    wb.save(os.path.join(out, "annotation.xlsx"))
    with open(os.path.join(base, "key.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "ocr_id"])
        w.writerows(enumerate(chosen, start=1))
    print(f"{n_signs} signs -> {out}; key -> {base}/key.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", choices=["second-auditor", "from-scratch"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    second_auditor(a.force) if a.package == "second-auditor" else from_scratch(a.force)
