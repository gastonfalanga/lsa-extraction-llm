import csv
import math
import random
import re
from collections import Counter, defaultdict

from openpyxl import load_workbook

RETURNED = "work/second_auditor/returned/planilla_completed.xlsx"
KEY = "work/second_auditor/key.csv"
AUDIT = "work/audit/audit_sheet.xlsx"
OUT = "work/second_auditor/results.md"
PAIRS = "work/second_auditor/verdict_pairs.csv"
JUDGED = {"Correct", "Wrong"}
PALM_EQ = {"Palm outward": "Palm forward", "Palm backward": "Palm inward"}
POS_EQ = {"space: Space in front of torso": "space: Space in front of chest"}


def pos(v):
    v = (v or "").strip()
    return POS_EQ.get(v, v)


def palm(v):
    v = v or ""
    m = re.search(r"Palm [a-z ]+?(?= \||$)", v)
    p = m.group(0).strip() if m else v.strip()
    return PALM_EQ.get(p, p)


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan"), float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, ((po - pe) / (1 - pe) if pe < 1 else float("nan"))


def fisher(a, b, c, d):
    n, r1, c1 = a + b + c + d, a + b, a + c

    def p(x):
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    obs = p(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


def main():
    with open(KEY, encoding="utf-8") as f:
        arm = {int(r["n"]): r["arm"] for r in csv.DictReader(f)}
    audit = {i: r for i, r in enumerate(load_workbook(AUDIT, read_only=True)["fields"].iter_rows(
        min_row=2, values_only=True), start=2)}
    wb = load_workbook(RETURNED, read_only=True)

    derived = []
    for r in list(wb["describir"].iter_rows(min_row=2, values_only=True)):
        if r[0] is None:
            continue
        n, present = int(r[0]), (r[5] or "").strip().lower()
        rows = {audit[int(k)][6]: int(k) for k in str(r[12]).split(";")}
        if present == "no":
            for field, k in rows.items():
                derived.append((n, k, field, "Not applicable", audit[k][8]))
            continue
        a_ip, a_io, a_fp, a_fo = pos(r[6]), palm(r[7]), r[9], r[10]
        a_fp = a_ip if a_fp in (None, "", "(sin cambio)") else pos(a_fp)
        a_fo = a_io if a_fo in (None, "", "(sin cambio)") else palm(a_fo)
        e = {f: audit[k][7] for f, k in rows.items()}
        e_ip, e_io = pos(e.get("initial_position")), palm(e.get("initial_orientation"))
        e_fp = e_ip if e.get("final_position") == "(absent)" else pos(e.get("final_position"))
        e_fo = e_io if e.get("final_orientation") == "(absent)" else palm(e.get("final_orientation"))
        mine = {"initial_position": a_ip == e_ip, "initial_orientation": a_io == e_io,
                "final_position": a_fp == e_fp, "final_orientation": a_fo == e_fo}
        for field, k in rows.items():
            derived.append((n, k, field, "Correct" if mine[field] else "Wrong", audit[k][8]))

    verified = []
    for r in list(wb["verificar"].iter_rows(min_row=2, values_only=True)):
        if r[0] is None:
            continue
        k = int(r[10])
        verified.append((int(r[0]), k, audit[k][6], r[7], audit[k][8]))

    def block(rows):
        pairs = [(v, g) for _, _, _, v, g in rows if v in JUDGED and g in JUDGED]
        po, k = kappa(pairs)
        wrong_ref = [v for v, g in pairs if g == "Wrong"]
        accepted = sum(1 for v in wrong_ref if v == "Correct")
        correct_ref = [v for v, g in pairs if g == "Correct"]
        rejected = sum(1 for v in correct_ref if v == "Wrong")
        own_acc = sum(1 for v, _ in pairs if v == "Correct") / len(pairs)
        ref_acc = sum(1 for _, g in pairs if g == "Correct") / len(pairs)
        return dict(n=len(pairs), po=po, k=k, wrong_ref=len(wrong_ref), accepted=accepted,
                    correct_ref=len(correct_ref), rejected=rejected, own_acc=own_acc, ref_acc=ref_acc,
                    signs=len({x[0] for x in rows}))

    d, v = block(derived), block(verified)
    p = fisher(v["accepted"], v["wrong_ref"] - v["accepted"], d["accepted"], d["wrong_ref"] - d["accepted"])

    def per_sign(rows):
        acc = defaultdict(lambda: [0, 0])
        for n, _, _, ver, g in rows:
            if g == "Wrong" and ver in JUDGED:
                acc[n][1] += 1
                acc[n][0] += ver == "Correct"
        return [a / b for a, b in acc.values() if b]
    ps_v, ps_d = per_sign(verified), per_sign(derived)

    acc = defaultdict(lambda: [0, 0])
    lab = {}
    for rows, name in ((derived, "describe"), (verified, "verify")):
        for n, _, _, ver, g in rows:
            lab[n] = name
            if ver in JUDGED and g in JUDGED:
                acc[n][0] += ver == "Correct"
                acc[n][1] += 1
    signs = [n for n in acc if acc[n][1]]

    def diff(labels):
        vv = [acc[n][0] / acc[n][1] for n in signs if labels[n] == "verify"]
        dd = [acc[n][0] / acc[n][1] for n in signs if labels[n] == "describe"]
        return sum(vv) / len(vv) - sum(dd) / len(dd)
    observed = diff(lab)
    rng, labels, hits, n_perm = random.Random(1), [lab[n] for n in signs], 0, 20000
    for _ in range(n_perm):
        rng.shuffle(labels)
        hits += abs(diff(dict(zip(signs, labels)))) >= abs(observed) - 1e-12
    p_perm = hits / n_perm

    by_field = defaultdict(list)
    for _, _, field, ver, g in derived:
        if ver in JUDGED and g in JUDGED:
            by_field[field].append((ver, g))

    lines = [
        "# Second auditor: results", "",
        "Generated by `code/analysis/second_auditor_results.py`. Reference: the first auditor's blind verdicts.", "",
        "## Agreement on drawn fields (describe arm, both auditors blind)", "",
        f"- Signs: {d['signs']}; fields judged by both: {d['n']}",
        f"- Agreement: {100 * d['po']:.1f}%; Cohen's kappa: {d['k']:.2f}",
        f"- Accuracy of the extraction as estimated by each auditor on these fields: second {100 * d['own_acc']:.1f}%, "
        f"first {100 * d['ref_acc']:.1f}%",
        "",
        "| Field | n | agreement | kappa |", "|---|---|---|---|",
    ]
    for field in ("initial_position", "initial_orientation", "final_position", "final_orientation"):
        po, k = kappa(by_field[field])
        lines.append(f"| {field} | {len(by_field[field])} | {100 * po:.1f}% | {k:.2f} |")
    lines += [
        "", "## Anchoring, randomized between signs", "",
        "| Arm | signs | fields | agreement with first auditor | kappa | first auditor's Wrong accepted as Correct | "
        "first auditor's Correct called Wrong | extraction accuracy as judged |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, b in (("blind (describe)", d), ("value in view (verify)", v)):
        lines.append(f"| {name} | {b['signs']} | {b['n']} | {100 * b['po']:.1f}% | {b['k']:.2f} | "
                     f"{b['accepted']}/{b['wrong_ref']} ({100 * b['accepted'] / max(b['wrong_ref'], 1):.1f}%) | "
                     f"{b['rejected']}/{b['correct_ref']} | {100 * b['own_acc']:.1f}% (first auditor: {100 * b['ref_acc']:.1f}%) |")
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    lines += [
        "", f"- **Main test (sign level, the randomized unit):** mean per-sign judged accuracy, verify minus describe = "
        f"{100 * observed:.1f} points; permutation p = {p_perm:.3f} ({len(signs)} signs, {n_perm} permutations).",
        f"- Field level, for reference only (fields are not independent): judged accuracy {100 * v['own_acc']:.1f}% vs "
        f"{100 * d['own_acc']:.1f}%.",
        f"- Fisher exact test, accepted vs not accepted Wrong fields, verify vs describe: p = {p:.4f} "
        "(field level; fields cluster within signs, so this p-value is optimistic).",
        f"- Sign level: mean share of the first auditor's Wrong fields accepted per sign: verify "
        f"{100 * mean(ps_v):.1f}% ({len(ps_v)} signs), describe {100 * mean(ps_d):.1f}% ({len(ps_d)} signs).",
        "- The first auditor's accuracy on each arm shows whether the two random halves differ in difficulty.",
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(PAIRS, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fields_row", "arm", "field", "second_auditor_verdict", "first_auditor_verdict"])
        for arm, rows in (("describe", derived), ("verify", verified)):
            for _, k, field, ver, g in rows:
                w.writerow([k, arm, field, ver or "", g or ""])
    print("\n".join(lines))


if __name__ == "__main__":
    main()
