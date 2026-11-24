import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict

from openpyxl import load_workbook

WORKBOOK = "work/audit/audit_sheet.xlsx"
LOG = "work/audit/text_scoring_log.csv"

HANDSHAPES = {
    "mano plana": "Flat hand", "miton": "Mitten", "b": "B", "angulo cerrado": "Closed angle",
    "angulo": "Angle", "cinco": "Five", "cuatro": "Four", "tres": "Three", "pulgar-mayor": "Thumb-middle",
    "pulgar mayor": "Thumb-middle", "mayor": "Middle finger", "dedos juntos": "Fingers together",
    "curva": "Curve", "ovalo": "Oval", "garra": "Claw", "puno": "Fist", "llave": "Key", "pulgar": "Thumb",
    "telefono": "Telephone", "indice": "Index", "gancho": "Hook", "cuernos": "Horns", "menique": "Pinky",
    "v-gancho": "V-hook", "uve-gancho": "V-hook", "v gancho": "V-hook", "v": "V", "uve": "V",
    "duo-gancho": "Duo-hook", "duo-pulgar": "Duo-thumb", "duo": "Duo", "l-ovalo": "L-oval", "l ovalo": "L-oval",
    "l curva": "Curved L", "l plegada": "Folded L", "l": "L", "pico": "Beak", "pinza-ovalo": "Pincer-oval",
    "pinza ovalo": "Pincer-oval", "pinza-pico": "Pincer-beak", "pinza pico": "Pincer-beak",
}
MANNERS = {
    "rotacion de muneca": "Wrist rotation", "rotacion alternada de muneca": "Wrist rotation",
    "rotacion de munecas": "Wrist rotation", "rotacion alternada de munecas": "Wrist rotation",
    "vibracion de dedos": "Vibratory",
    "quiebre de muneca": "Wrist break", "quiebre de munecas": "Wrist break", "quiebre": "Wrist break", "detenimiento brusco": "Abrupt stop",
    "oscilatorio": "Oscillatory", "lineal": "Linear", "curvo": "Curved", "circular": "Circular",
    "vibratorio": "Vibratory", "vibracion": "Vibratory", "rebote": "Bouncing", "pianoteo": "Piano-playing",
    "golpeteo": "Tapping", "frotacion": "Rubbing", "tincazo": "Flicking", "lento": "Slow",
}
PATHS = {
    "opuesto convergente": "Opposite convergent", "opuesto divergente": "Opposite divergent",
    "hacia abajo": "Downward", "hacia arriba": "Upward", "hacia adelante": "Forward", "hacia atras": "Backward",
    "hacia adentro": "Inward", "hacia afuera": "Outward", "divergente": "Divergent", "convergente": "Convergent",
    "alternado": "Alternating", "alternada": "Alternating", "simultaneo": "Simultaneous", "simultanea": "Simultaneous",
}
FILLER = {"con", "y", "de", "la", "el", "en", "a", "al", "mov", "movimiento", "final", "inicial"}
LEAVES_PATH_TO_DRAWING = {"desplazamiento"}
CONTACT_WORDS = {"golpe", "superpuesta", "superpuestas"}
REPEATED_MANNERS = {"Tapping", "Piano-playing"}
VOCAB = {w for d in (HANDSHAPES, MANNERS, PATHS) for k in d for w in k.split()} | FILLER | LEAVES_PATH_TO_DRAWING | CONTACT_WORDS
DRAWING_ONLY_FIELDS = {"initial_position", "initial_orientation", "final_position", "final_orientation"}

CODE = re.compile(r"(?<![A-Za-z])C\s*\.?\s*([IF])\s*\.?\s*(?:M\s*\.?\s*([DI])\s*\.?)?(?![a-z])\s*:?")
MOV = re.compile(r"(?i)(?<![a-z])mov(?![a-z])\s*\.?\s*(?:M\s*\.?\s*([DI])\s*\.?)?\s*[:;]?")
CNM = re.compile(r"C\s*\.?\s*N\s*\.?\s*M\s*\.?\s*:?")
VARIANTE = re.compile(r"(?i)variantes?\s*:?")
LABEL = re.compile(r"(?:^|\s)([A-D])\s*[.:)]?\s+(?=C\s*\.?\s*[IF]|Mov|[1-4]\s*[.):]?\s)")
COMPONENT = re.compile(r"(?:^|\n|(?<=[A-D][.:)\s]))\s*([1-4])\s*[.):]?\s*(?=\n|C\s*\.?\s*[IF]|Mov)")

TEXT_LAYER_FIXES = [
    (re.compile(r"(?<![A-Za-z])M\s*\.\s*O\s*\."), "M.D."),
    (re.compile(r"(?<![A-Za-z])M\s*\.\s*[l1!]\s*\."), "M.I."),
    (re.compile(r"(?<![A-Za-z])C\s*\.?\s*[l1!]\s*\.?\s*(?=M\s*\.)"), "C.I."),
    (re.compile(r"(?<![A-Za-z])C\s*\.\s*[fE]\s*\.?\s*(?=M\s*\.)"), "C.F."),
    (re.compile(r"(?<![A-Za-z])C\s*\.\s*[lL1!](?![a-z])\s*\.?"), "C.I."),
    (re.compile(r"(?<![A-Za-z])C\s*\.\s*\.\s*(?=M\s*\.)"), "C.I."),
    (re.compile(r"(?<![A-Za-z])M\s+o\s*v(?![a-z])"), "Mov"),
]


def norm(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[\"'“”.,;:()]", " ", text)).strip()


def clean_text_layer(text):
    for pattern, repl in TEXT_LAYER_FIXES:
        text = pattern.sub(repl, text)
    return text


def repair_words(words):
    out = []
    for w in words:
        if out and out[-1] + w in VOCAB and (out[-1] not in VOCAB or w not in VOCAB):
            out[-1] += w
        elif w not in VOCAB and w.startswith("l") and "i" + w[1:] in VOCAB:
            out.append("i" + w[1:])
        else:
            out.append(w)
    return out


def take_terms(text, lexicon):
    found, rest = [], f" {' '.join(repair_words(norm(text).split()))} "
    for term in sorted(lexicon, key=len, reverse=True):
        pattern = f" {term} "
        while pattern in rest:
            found.append(lexicon[term])
            rest = rest.replace(pattern, " ", 1)
    return found, [w for w in rest.split() if w not in FILLER]


def parse(printed):
    printed = clean_text_layer(printed)
    marks = []
    for m in CODE.finditer(printed):
        marks.append((m.start(), m.end(), "code", (m.group(1), m.group(2))))
    for m in MOV.finditer(printed):
        marks.append((m.start(), m.end(), "mov", m.group(1)))
    for m in CNM.finditer(printed):
        marks.append((m.start(), m.end(), "cnm", None))
    for m in VARIANTE.finditer(printed):
        marks.append((m.start(), m.end(), "variante", None))
    for m in LABEL.finditer(printed):
        marks.append((m.start(1), m.end(1), "label", m.group(1).upper()))
    for m in COMPONENT.finditer(printed):
        marks.append((m.start(1), m.end(1), "component", int(m.group(1))))
    marks.sort()
    marks = [m for m in marks if not (m[2] == "code" and any(c[2] == "cnm" and c[0] <= m[0] < c[1] for c in marks))]

    variants, current = [], None

    def new_variant(base=None):
        v = {"config": dict(base["config"]) if base else {}, "mov": {}, "cnm": None, "notes": [], "two_hands_codes": False}
        if base:
            v["two_hands_codes"] = base["two_hands_codes"]
        variants.append(v)
        return v

    for i, (start, end, kind, value) in enumerate(marks):
        content = printed[end:marks[i + 1][0] if i + 1 < len(marks) else len(printed)].strip()
        if kind == "label":
            current = new_variant(variants[0] if variants and value != "A" and not variants[0]["config"] == {} and False else None)
            continue
        if kind == "variante":
            if i + 1 == len(marks):
                for v in variants:
                    v["prose_variants"] = content
                continue
            current = new_variant(variants[-1] if variants else None)
            current["mov"] = {}
            continue
        if kind == "component":
            if current is None:
                current = new_variant()
            current["component"] = value
            if value > 1:
                current["multi_component"] = True
            continue
        if current is None:
            current = new_variant()
        if kind == "code":
            state = "initial" if value[0] == "I" else "final"
            hands = {"D": ["dominant_hand"], "I": ["non_dominant_hand"], None: ["dominant_hand", "non_dominant_hand"]}[value[1]]
            if state == "final" and value[1] is None:
                hands = [h for h in hands if ("initial", h) in current["config"]] or hands
            elif value[1] in (None, "I"):
                current["two_hands_codes"] = True
            alternatives = [a for a in re.split(r"\s+o\s+", content) if a.strip()]
            if current.get("component", 1) > 1:
                continue
            for hand in hands:
                current["config"][(state, hand)] = alternatives
        elif kind == "mov":
            target = {"D": ["dominant_hand"], "I": ["non_dominant_hand"], None: ["generic"]}[value]
            if set(target) & set(current["mov"]):
                current["multi_component"] = True
            for hand in target:
                current["mov"][hand] = content
        elif kind == "cnm":
            current["cnm"] = content
    expanded = []
    for v in variants:
        alt_keys = [k for k, alts in v["config"].items() if len(alts) > 1]
        if alt_keys:
            n = max(len(v["config"][k]) for k in alt_keys)
            for j in range(n):
                copy = {**v, "config": {k: [alts[min(j, len(alts) - 1)]] for k, alts in v["config"].items()}}
                expanded.append(copy)
        else:
            expanded.append(v)
    return expanded


def handshape(text):
    values, rest = take_terms(text, HANDSHAPES)
    modifiers = [w for w in rest if w not in HANDSHAPES]
    return (values[0] if len(values) == 1 else None), modifiers


def expected_movement(mov_text, config_modifiers=()):
    manners, rest = take_terms(mov_text, MANNERS)
    paths, rest = take_terms(" ".join(rest), PATHS)
    contact = (any(w in CONTACT_WORDS for w in rest) or any(w in CONTACT_WORDS for w in config_modifiers)
               or "Tapping" in manners or "Rubbing" in manners)
    repetition = bool(REPEATED_MANNERS & set(manners)) or {"Divergent", "Convergent"} <= set(paths)
    path_to_drawing = any(w in LEAVES_PATH_TO_DRAWING for w in rest)
    unknown = [w for w in rest if w not in CONTACT_WORDS | LEAVES_PATH_TO_DRAWING | {"golpe"}]
    return {"manner": manners, "path": paths, "contact": contact, "repetition": repetition,
            "path_to_drawing": path_to_drawing, "unknown": unknown, "hit": "golpe" in rest}


def split_list(value):
    return sorted(v.strip() for v in str(value).split(";") if v.strip()) if value and value != "(absent)" else []


def score_sign(printed, rows, variant_labels):
    parsed = parse(printed)
    out = {}
    if any(v.get("prose_variants") for v in parsed):
        reason = f"variants described in prose ('{parsed[0]['prose_variants']}'): judge by eye"
        for key in rows:
            out[key] = (None, "", "", "", reason)
        return out, parsed
    if len(parsed) != len(variant_labels):
        reason = f"text describes {len(parsed)} variant(s), extraction has {len(variant_labels)}: judge by eye"
        for key in rows:
            out[key] = (None, "", "", "", reason)
        return out, parsed
    by_variant = dict(zip(variant_labels, parsed))
    for (variant, component, hand, field), extracted in rows.items():
        if field in DRAWING_ONLY_FIELDS:
            continue
        v = by_variant[variant]
        if field == "non_manual_components":
            if v["cnm"] is None:
                out[(variant, component, hand, field)] = ("Correct", "", "No", "", "no C.N.M. printed") if extracted == "(absent)" \
                    else (None, "", "No", "", "non-manuals not printed: judge the drawing")
            else:
                out[(variant, component, hand, field)] = (None, "", "Yes", "", f"C.N.M. printed ('{v['cnm']}'): compare by eye")
            continue
        if component not in (1, "1", None) or (v.get("multi_component") and field != "initial_configuration"):
            out[(variant, component, hand, field)] = (None, "", "", "", "multi-component sign: judge by eye")
            continue
        if field in ("initial_configuration", "final_configuration"):
            state = field.split("_")[0]
            printed_cfg = v["config"].get((state, hand))
            if printed_cfg is None:
                if state == "final":
                    continue
                out[(variant, component, hand, field)] = (None, "", "No", "", "no handshape code for this hand")
                continue
            value, modifiers = handshape(printed_cfg[0])
            if value is None:
                out[(variant, component, hand, field)] = (None, "", "Yes", "", f"could not map '{printed_cfg[0]}'")
            elif value == extracted:
                out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", f"printed '{printed_cfg[0].strip()}'")
            else:
                err = "Abbreviation misread" if extracted == "(absent)" else "Other (see notes)"
                out[(variant, component, hand, field)] = ("Wrong", value, "Yes", err, f"printed '{printed_cfg[0].strip()}' = {value}")
            continue
        if hand in v["mov"]:
            mov_text, applies = v["mov"][hand], True
        elif "generic" in v["mov"]:
            mov_text, applies = v["mov"]["generic"], None
        elif v["mov"]:
            mov_text, applies = "", False
        else:
            mov_text, applies = "", None
        if applies is False:
            ok = extracted == "(absent)"
            out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", "movement printed for the other hand only") if ok \
                else ("Wrong", "(absent)", "Yes", "Hand count or movement distribution", "movement printed for the other hand only")
            continue
        if applies is None and (not mov_text or (hand == "non_dominant_hand" and extracted == "(absent)")):
            out[(variant, component, hand, field)] = (None, "", "No", "", "generic Mov.: whether this hand moves depends on the drawing")
            continue
        config_modifiers = handshape(v["config"].get(("initial", hand), [""])[0])[1]
        exp = expected_movement(mov_text, config_modifiers)
        if exp["unknown"]:
            out[(variant, component, hand, field)] = (None, "", "Yes", "", f"unmapped words in Mov.: {' '.join(exp['unknown'])}")
            continue
        got_list = split_list(extracted)
        if field == "movement_manner":
            want = sorted(exp["manner"])
            if not want:
                out[(variant, component, hand, field)] = (None, "", "No", "", "no manner printed: judge the drawing")
            elif got_list == want:
                out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", f"printed '{mov_text}'")
            elif set(want) < set(got_list):
                out[(variant, component, hand, field)] = (None, "", "Yes", "", f"extra manner beyond the text ({', '.join(set(got_list) - set(want))}): check the drawing")
            else:
                out[(variant, component, hand, field)] = ("Wrong", "; ".join(want), "Yes", "Other (see notes)", f"printed '{mov_text}'")
        elif field == "movement_path":
            want = sorted(exp["path"])
            if not want or exp["path_to_drawing"]:
                out[(variant, component, hand, field)] = (None, "", "No", "", "direction not printed: judge the drawing")
            elif got_list == want:
                out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", f"printed '{mov_text}'")
            elif set(want) < set(got_list):
                out[(variant, component, hand, field)] = (None, "", "Yes", "", f"extra path beyond the text ({', '.join(set(got_list) - set(want))}): check the drawing")
            else:
                out[(variant, component, hand, field)] = ("Wrong", "; ".join(want), "Yes", "Other (see notes)", f"printed '{mov_text}'")
        elif field in ("movement_contact", "movement_repetition"):
            want = exp["contact"] if field == "movement_contact" else exp["repetition"]
            got = str(extracted)
            if want and got == "True":
                out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", "printed trigger")
            elif want:
                err = "Text detail ignored"
                out[(variant, component, hand, field)] = ("Wrong", "True", "Yes", err, f"printed '{mov_text}' implies {field.split('_')[1]}")
            elif got in ("False", "(absent)"):
                out[(variant, component, hand, field)] = ("Correct", "", "Yes", "", "no printed trigger")
            else:
                out[(variant, component, hand, field)] = (None, "", "No", "", f"{field.split('_')[1]} not printed: check the drawing")
    return out, parsed


def sign_level(parsed, hand_count, variant_count):
    two = any(v["two_hands_codes"] for v in parsed) or any("non_dominant_hand" in v["mov"] for v in parsed)
    want_hands = "2" if two else "1"
    hands = ("Correct", "", "") if str(hand_count) == want_hands else (None, want_hands, "")
    variants = ("Correct", "", "") if int(variant_count) == len(parsed) else ("Wrong", str(len(parsed)), "Missed / duplicated / miscounted entry")
    if any(v.get("prose_variants") for v in parsed):
        return {"hand_count": hands}
    return {"hand_count": hands, "variant_count": variants}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate", metavar="SET", help="compare decisions with verdicts already in the workbook for this set (e.g. pilot)")
    args = ap.parse_args()

    if os.path.exists(os.path.join(os.path.dirname(WORKBOOK), "~$" + os.path.basename(WORKBOOK))):
        sys.exit("The workbook is open in Excel. Close it first.")

    wb = load_workbook(WORKBOOK)
    ws_signs, ws_fields = wb["signs"], wb["fields"]
    header = [c.value for c in ws_signs[1]]
    col = {name: i + 1 for i, name in enumerate(header)}

    field_rows = defaultdict(list)
    for r in range(2, ws_fields.max_row + 1):
        field_rows[ws_fields[f"B{r}"].value].append(r)

    log, agree, disagree, handed = [], 0, [], 0
    for sr in range(2, ws_signs.max_row + 1):
        set_name = ws_signs.cell(sr, col["set"]).value
        printed = ws_signs.cell(sr, col["printed_text"]).value
        if not printed or (args.validate and set_name != args.validate):
            continue
        ocr_id = ws_signs.cell(sr, col["ocr_id"]).value
        rows, row_of, labels = {}, {}, []
        for r in field_rows[ocr_id]:
            key = (ws_fields[f"D{r}"].value, ws_fields[f"E{r}"].value, ws_fields[f"F{r}"].value or "", ws_fields[f"G{r}"].value)
            rows[key] = ws_fields[f"H{r}"].value
            row_of[key] = r
            if key[0] not in labels:
                labels.append(key[0])
        decisions, parsed = score_sign(printed, rows, labels)
        level = sign_level(parsed, ws_signs.cell(sr, col["hand_count_extracted"]).value,
                           ws_signs.cell(sr, col["variant_count_extracted"]).value)

        for key, (verdict, correct, printed_in, err, reason) in decisions.items():
            r = row_of[key]
            existing = ws_fields[f"I{r}"].value
            if args.validate:
                if existing is None and verdict is None:
                    continue
                same = (existing or "Correct") == (verdict or "?")
                agree += same
                if not same:
                    disagree.append((ocr_id, key, ws_fields[f"H{r}"].value, existing, verdict, reason))
                continue
            if existing or str(ws_fields[f"N{r}"].value or "").startswith("[text]"):
                continue
            if verdict is None:
                handed += 1
            else:
                ws_fields[f"I{r}"] = verdict
                ws_fields[f"J{r}"] = correct or None
                ws_fields[f"L{r}"] = err or None
                if verdict == "Wrong":
                    ws_fields[f"M{r}"] = "No"
            if printed_in:
                ws_fields[f"K{r}"] = printed_in
            ws_fields[f"N{r}"] = f"[text] {reason}" + (f" | {ws_fields[f'N{r}'].value}" if ws_fields[f"N{r}"].value else "")
            log.append({"ocr_id": ocr_id, "row": r, "variant": key[0], "hand": key[2], "field": key[3],
                        "extracted": rows[key], "verdict": verdict or "AUDITOR", "correct_value": correct,
                        "error_type": err, "reason": reason, "printed_text": printed})
        for field, (verdict, correct, err) in level.items():
            cell = ws_signs.cell(sr, col[f"{field}_verdict"])
            if verdict is None:
                if args.validate or cell.value:
                    continue
                note = f"[text] the text suggests {correct} hand(s), the model has {ws_signs.cell(sr, col['hand_count_extracted']).value}: judge the drawing"
                old = ws_signs.cell(sr, col["notes"]).value
                ws_signs.cell(sr, col["notes"], f"{old} | {note}" if old else note)
                log.append({"ocr_id": ocr_id, "row": sr, "variant": "", "hand": "", "field": field, "extracted": "",
                            "verdict": "AUDITOR", "correct_value": correct, "error_type": err, "reason": note,
                            "printed_text": printed})
                continue
            if args.validate:
                same = (cell.value or "Correct") == verdict
                agree += same
                if not same:
                    disagree.append((ocr_id, field, "", cell.value, verdict, "sign level"))
                continue
            if cell.value:
                continue
            cell.value = verdict
            if correct:
                ws_signs.cell(sr, col[f"{field}_correct_value"], correct)
            log.append({"ocr_id": ocr_id, "row": sr, "variant": "", "hand": "", "field": field, "extracted": "",
                        "verdict": verdict, "correct_value": correct, "error_type": err, "reason": "sign level",
                        "printed_text": printed})

    if args.validate:
        print(f"agree {agree}, disagree {len(disagree)}")
        for d in disagree:
            print("  ", d)
        return
    for entry in log:
        print(entry["ocr_id"], entry["field"], entry["verdict"], "|", entry["reason"])
    print(f"\n{len(log)} decisions, {handed} handed back to the auditor")
    if args.dry_run:
        return
    wb.save(WORKBOOK)
    new_file = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(log[0]) if log else ["ocr_id"], quoting=csv.QUOTE_ALL)
        if new_file:
            writer.writeheader()
        writer.writerows(log)
    print(f"Saved. Now run: python code/audit/build_audit_sheet.py --upgrade")


if __name__ == "__main__":
    main()
