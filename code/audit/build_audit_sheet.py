import argparse
import csv
import glob
import json
import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SAMPLE_CSV = "work/audit/audit_sample.csv"
RAW_DIR = "work/outputs/raw_ocr_history/first_commit"
OUTPUT = "work/audit/audit_sheet.xlsx"

VERDICTS = ["Correct", "Wrong", "Ambiguous in source", "Source inconsistent", "Not applicable"]
YES_NO = ["Yes", "No"]
ERROR_TYPES = [
    "Abbreviation misread",
    "Initial/final state swapped",
    "Arrow semantics",
    "Wrong inferred value",
    "Catalog gap (nearest value forced)",
    "Hand count or movement distribution",
    "Missed / duplicated / miscounted entry",
    "Sense split",
    "Text noise",
    "Text detail ignored",
    "Other (see notes)",
]

HAND_FIELDS = [
    ("initial_configuration", ("initial_configuration",)),
    ("initial_position", ("initial_position",)),
    ("initial_orientation", ("initial_orientation",)),
    ("movement_manner", ("movement", "manner")),
    ("movement_path", ("movement", "path")),
    ("movement_contact", ("movement", "contact")),
    ("movement_repetition", ("movement", "repetition")),
    ("final_configuration", ("final_configuration",)),
    ("final_position", ("final_position",)),
    ("final_orientation", ("final_orientation",)),
]
DRAWING_ONLY_FIELDS = {"initial_position", "initial_orientation", "final_position", "final_orientation"}
WRITTEN_FIELDS = {"initial_configuration", "final_configuration", "movement_manner", "movement_path",
                  "movement_contact", "movement_repetition", "non_manual_components"}
VISUAL_FIELDS = DRAWING_ONLY_FIELDS | {"final_configuration"}
SIGN_FIELDS = ["gloss", "hand_count", "variant_count", "component_counts"]
VISUAL_SIGN_FIELDS = {"gloss", "component_counts"}
TO_FILL = PatternFill("solid", fgColor="FFF2A8")
BY_SCRIPT = PatternFill("solid", fgColor="E7E7E7")

README = [
    "Audit of the raw OCR output. Ground truth = the printed entry (text and drawing).",
    "",
    "Only YELLOW cells are filled by hand. GREY cells are scored by script from printed_text; leave them empty.",
    "",
    "How to fill:",
    "- Audit the pilot signs (set = pilot) first; they test the sheet and do not count.",
    "- signs sheet, printed_text: copy the sign's description box exactly as printed (C.I., C.I.M.D., C.F., Mov., C.N.M., Variante...),",
    "  including words like 'superpuesta', the quotes and the variant letters. The script compares the written fields against it.",
    "- Then judge by eye only the yellow rows of the fields sheet (positions, orientations, final configuration)",
    "  and the number of components (signs sheet), against the drawing.",
    "- Only exceptions are filled. When a sign is done, set reviewed = Yes in the signs sheet:",
    "  from then on, every empty verdict of that sign (signs and fields sheets) counts as Correct.",
    "- signs sheet: reviewed, printed_text, and a verdict for gloss and component_counts only if it is not Correct.",
    "- timing sheet: time whole batches of 10 signs, one row per batch and task (text = transcriptions, visual = yellow cells),",
    "  in seconds. The seconds column of the signs sheet is only for signs timed one by one.",
    "- fields sheet: a verdict only for yellow rows that are not Correct. If Wrong, add an error type; the correct value is optional",
    "  (write it when it is quick; never needed for orientations, which the source never writes).",
    "- catalog_gap is Yes or No only; explanations go in notes.",
    "- printed_in_text: Yes if the printed text states this field (e.g. an abbreviation gives it); No if it can only come from the drawing.",
    "  Fill it for every row that applies, whatever the verdict.",
    "  printed_in_text is prefilled: 'No' for positions and orientations (the dictionary's introduction says they are never written,",
    "  only drawn) and 'Yes' for configurations, movement and non-manuals that the model extracted. Change it only when an entry differs.",
    "- '(absent)' means the model left the field out. Correct if the field really does not apply; Wrong if it was missed.",
    "",
    "Error criteria:",
    "- This audit measures whether the extraction matches the printed page, nothing else.",
    "  Do not use your own knowledge of LSA to judge: if the page shows it, it is right, even if the sign is signed differently today.",
    "  Write what you know as an LSA signer in notes (prefix 'LSA:'); it is useful for the dataset, but it does not change the verdict.",
    "- Ambiguous drawing or text -> 'Ambiguous in source'. It is reported separately and is not an error.",
    "- Text and drawing contradict each other (e.g. the text says Key and the drawing shows L) -> 'Source inconsistent'.",
    "- Variant with no drawing: drawn fields -> 'Not applicable', with a note starting '[undrawn variant]'.",
    "- Orientation: the catalog has no 'Palm backward'. A palm pointing to the signer's back counts as 'Palm inward', so 'Palm inward' covers both the side towards the opposite hand and the back.",
    "- Orientation: 'Palm outward' and 'Palm forward' count as the same value.",
    "- Location: 'Space in front of torso' and 'Space in front of chest' count as the same value.",
    "- Repetition: vibration, rubbing and oscillation do not count as repetition on their own; tapping and piano-playing do.",
    "  Write in notes what each one shows and which one the model followed. Not an extraction error.",
    "- Spanish senses printed in grey are senses of the Spanish word that the sign does not share (dictionary convention).",
    "  If the model turned a grey sense into a meaning, note it in the signs sheet (notes) as 'grey sense'.",
    "- A nearest value chosen because the right one is not in the catalog -> Wrong + 'Catalog gap (nearest value forced)' + catalog_gap = Yes.",
    "  It is a coverage error, not a reading error.",
    "- Judge with the extraction-time schema: position is body OR space; contact lives in movement.",
    "- Movement path comes from arrows or from the text. A movement shown only by a change between the dashed (initial)",
    "  and solid (final) drawing, with no arrow, is not a missing path: if the manner and contact already imply it (e.g. tapping",
    "  between both hands), path '(absent)' is Correct; if the change of place is lost, mark final_position Wrong instead.",
    "- Whole sign correct = every applicable field is Correct (computed at analysis, not filled here).",
    "- Do not look at ocr_confidence or visually_deduced_fields while auditing: they are left out on purpose.",
]


def get_path(obj, path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def render(value):
    if value is None:
        return "(absent)"
    if isinstance(value, dict):
        return " | ".join(f"{k}: {render(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(render(v) for v in value)
    return str(value)


EXCLUDED_FILES = {"lote_156.json"}


def load_raw(raw_dir):
    signs = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "lote_*.json"))):
        if os.path.basename(path) in EXCLUDED_FILES:
            continue
        with open(path, encoding="utf-8") as f:
            for sign in json.load(f):
                signs[sign["sign_id"]] = sign
    return signs


def style_sheet(ws, widths):
    header_fill = PatternFill("solid", fgColor="DDDDDD")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def add_dropdown(ws, list_range, column_letter, n_rows):
    dv = DataValidation(type="list", formula1=f"=lists!{list_range}", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{column_letter}2:{column_letter}{n_rows + 1}")


def write_readme_and_lists(wb):
    ws_readme = wb["README"] if "README" in wb.sheetnames else wb.create_sheet("README", 0)
    ws_readme.delete_rows(1, ws_readme.max_row)
    for line in README:
        ws_readme.append([line])
    ws_readme.column_dimensions["A"].width = 140

    if "timing" not in wb.sheetnames:
        ws_timing = wb.create_sheet("timing")
        ws_timing.append(["batch", "task", "signs", "seconds", "notes"])
        ws_timing.column_dimensions["E"].width = 60

    ws_lists = wb["lists"] if "lists" in wb.sheetnames else wb.create_sheet("lists")
    ws_lists.delete_rows(1, ws_lists.max_row)
    for col, values in enumerate([VERDICTS, YES_NO, ERROR_TYPES], start=1):
        for row, value in enumerate(values, start=1):
            ws_lists.cell(row=row, column=col, value=value)


def apply_layout(wb):
    ranges = {
        "verdict": f"$A$1:$A${len(VERDICTS)}",
        "yes_no": f"$B$1:$B${len(YES_NO)}",
        "error": f"$C$1:$C${len(ERROR_TYPES)}",
    }
    ws_signs, ws_fields = wb["signs"], wb["fields"]
    for ws in (ws_signs, ws_fields):
        ws.data_validations.dataValidation = []

    header = [c.value for c in ws_signs[1]]
    letter = {name: ws_signs.cell(row=1, column=i + 1).column_letter for i, name in enumerate(header)}
    n_signs = ws_signs.max_row - 1
    for field in SIGN_FIELDS:
        add_dropdown(ws_signs, ranges["verdict"], letter[f"{field}_verdict"], n_signs)
    add_dropdown(ws_signs, ranges["yes_no"], letter["reviewed"], n_signs)
    for row in range(2, n_signs + 2):
        for field in SIGN_FIELDS:
            fill = TO_FILL if field in VISUAL_SIGN_FIELDS else BY_SCRIPT
            ws_signs[f"{letter[f'{field}_verdict']}{row}"].fill = fill
            ws_signs[f"{letter[f'{field}_correct_value']}{row}"].fill = fill
        for name in ("reviewed", "seconds", "printed_text"):
            ws_signs[f"{letter[name]}{row}"].fill = TO_FILL

    n_fields = ws_fields.max_row - 1
    add_dropdown(ws_fields, ranges["verdict"], "I", n_fields)
    add_dropdown(ws_fields, ranges["yes_no"], "K", n_fields)
    add_dropdown(ws_fields, ranges["error"], "L", n_fields)
    add_dropdown(ws_fields, ranges["yes_no"], "M", n_fields)
    for row in range(2, n_fields + 2):
        handed_back = not ws_fields[f"I{row}"].value and str(ws_fields[f"N{row}"].value or "").startswith("[text]")
        fill = TO_FILL if ws_fields[f"G{row}"].value in VISUAL_FIELDS or handed_back else BY_SCRIPT
        for column in "IJLM":
            ws_fields[f"{column}{row}"].fill = fill


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="overwrite an existing workbook")
    parser.add_argument("--upgrade", action="store_true",
                        help="keep the existing workbook and its entries; refresh README, lists, columns, dropdowns and colours")
    args = parser.parse_args()

    if args.upgrade:
        wb = load_workbook(OUTPUT)
        ws_signs = wb["signs"]
        if "printed_text" not in [c.value for c in ws_signs[1]]:
            ws_signs.cell(row=1, column=ws_signs.max_column + 1, value="printed_text")
        write_readme_and_lists(wb)
        apply_layout(wb)
        style_sheet(ws_signs, {"B": 11, "C": 11, "D": 16, "G": 22})
        ws_signs.column_dimensions[ws_signs.cell(row=1, column=ws_signs.max_column).column_letter].width = 60
        wb.save(OUTPUT)
        print(f"Upgraded {OUTPUT} (entries kept)")
        return

    if os.path.exists(OUTPUT) and not args.force:
        sys.exit(f"{OUTPUT} already exists and may contain audit work. Use --force to overwrite it.")

    with open(SAMPLE_CSV, encoding="utf-8-sig") as f:
        sample = list(csv.DictReader(f))
    raw = load_raw(RAW_DIR)
    sample.sort(key=lambda r: (r["set"] != "pilot", r["ocr_id"]))

    wb = Workbook()
    wb.active.title = "README"
    write_readme_and_lists(wb)

    ws_signs = wb.create_sheet("signs", 1)
    sign_header = ["set", "ocr_id", "id", "batch", "printed_page", "slot_on_page"]
    for field in SIGN_FIELDS:
        sign_header += [f"{field}_extracted", f"{field}_verdict", f"{field}_correct_value"]
    sign_header += ["reviewed", "seconds", "notes", "printed_text"]
    ws_signs.append(sign_header)

    ws_fields = wb.create_sheet("fields", 2)
    ws_fields.append([
        "set", "ocr_id", "gloss", "variant", "component", "hand", "field", "extracted_value",
        "verdict", "correct_value", "printed_in_text", "error_type", "catalog_gap", "notes",
    ])

    for row in sample:
        sign = raw[row["ocr_id"]]
        variants = sign.get("sign_variants", [])
        components = [c for v in variants for c in v.get("sequential_components", [])]
        two_hands = any("non_dominant_hand" in c for c in components)
        sign_values = [
            sign.get("spanish_word", ""),
            "2" if two_hands else "1",
            str(len(variants)),
            ", ".join(str(len(v.get("sequential_components", []))) for v in variants),
        ]
        line = [row["set"], row["ocr_id"], row["id"], row["source_batch_file"],
                row["source_page_ocr"], row["sign_index_on_page"]]
        for value in sign_values:
            line += [value, "", ""]
        ws_signs.append(line + ["", "", "", ""])

        for v_index, variant in enumerate(variants, start=1):
            v_label = variant.get("variant_label") or str(v_index)
            for component in variant.get("sequential_components", []):
                c_order = component.get("component_order")
                base = [row["set"], row["ocr_id"], sign.get("spanish_word", ""), v_label, c_order]
                for hand in ("dominant_hand", "non_dominant_hand"):
                    hand_data = component.get(hand)
                    if hand_data is None:
                        continue
                    for field, path in HAND_FIELDS:
                        value = get_path(hand_data, path)
                        if field in DRAWING_ONLY_FIELDS:
                            printed = "No"
                        elif field in WRITTEN_FIELDS and value is not None:
                            printed = "Yes"
                        else:
                            printed = ""
                        ws_fields.append(base + [hand, field, render(value), "", "", printed, "", "", ""])
                nmc = component.get("non_manual_components")
                ws_fields.append(base + ["", "non_manual_components", render(nmc), "", "", "Yes" if nmc else "", "", "", ""])

    n_signs, n_fields = ws_signs.max_row - 1, ws_fields.max_row - 1
    apply_layout(wb)
    style_sheet(ws_signs, {"B": 11, "C": 11, "D": 16, "G": 22, "V": 60})
    style_sheet(ws_fields, {"B": 11, "C": 20, "F": 18, "G": 22, "H": 40, "I": 18, "J": 25, "K": 10, "L": 30, "N": 30})

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    print(f"{n_signs} signs, {n_fields} field rows -> {OUTPUT}")


if __name__ == "__main__":
    main()
