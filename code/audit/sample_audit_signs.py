import argparse
import csv
import glob
import json
import os
import random
import sys
from collections import defaultdict

DEFAULT_RAW_DIR = "work/outputs/raw_ocr_history/first_commit"
EXCLUDED_FILES = {"lote_156.json"}
ID_MAPPING_CSV = "backups/id_mapping.csv"
DEFAULT_OUTPUT = "work/audit/audit_sample.csv"


def load_raw_signs(raw_dir):
    files = sorted(f for f in glob.glob(os.path.join(raw_dir, "lote_*.json"))
                   if os.path.basename(f) not in EXCLUDED_FILES)
    if not files:
        sys.exit(f"No lote_*.json files found in {raw_dir}")
    signs = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            signs.extend(json.load(f))
    return signs, len(files)


def components(sign):
    for variant in sign.get("sign_variants", []):
        yield from variant.get("sequential_components", [])


def stratum_of(sign):
    two_hands = any("non_dominant_hand" in c for c in components(sign))
    multi = any(len(v.get("sequential_components", [])) > 1 for v in sign.get("sign_variants", []))
    nmc = any(c.get("non_manual_components") for c in components(sign))
    return ("two" if two_hands else "one", "multi" if multi else "single", "yes" if nmc else "no")


def allocate(sizes, total, minimum):
    population = sum(sizes.values())
    if total > population:
        sys.exit(f"Sample size {total} is larger than the population ({population})")

    alloc = {s: min(minimum, n) for s, n in sizes.items()}
    remaining = total - sum(alloc.values())
    if remaining < 0:
        sys.exit(f"--min-per-stratum {minimum} needs {sum(alloc.values())} signs, more than --size {total}")

    room = {s: sizes[s] - alloc[s] for s in sizes}
    room_total = sum(room.values())
    quotas = {s: remaining * room[s] / room_total for s in sizes} if room_total else {s: 0 for s in sizes}
    for s in sizes:
        alloc[s] += int(quotas[s])
    leftover = total - sum(alloc.values())
    by_remainder = sorted(sizes, key=lambda s: (quotas[s] - int(quotas[s]), s), reverse=True)
    for s in by_remainder:
        if leftover == 0:
            break
        if alloc[s] < sizes[s]:
            alloc[s] += 1
            leftover -= 1
    return alloc


def load_id_mapping():
    if not os.path.exists(ID_MAPPING_CSV):
        return {}
    with open(ID_MAPPING_CSV, encoding="utf-8-sig") as f:
        return {row["ocr_id"]: row["id"] for row in csv.DictReader(f)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR, help="folder with the raw lote_*.json files")
    parser.add_argument("--size", type=int, default=150, help="total sample size")
    parser.add_argument("--seed", type=int, default=20261029, help="random seed")
    parser.add_argument("--min-per-stratum", type=int, default=10, help="minimum signs per stratum")
    parser.add_argument("--pilot", type=int, default=10, help="extra signs for a pilot, outside the sample")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="CSV file to write")
    args = parser.parse_args()

    signs, n_files = load_raw_signs(args.raw_dir)
    signs.sort(key=lambda s: s["sign_id"])

    strata = defaultdict(list)
    for sign in signs:
        strata[stratum_of(sign)].append(sign)

    print(f"Raw OCR: {len(signs)} signs in {n_files} files ({args.raw_dir})\n")
    print(f"{'hands':<6} {'components':<11} {'nmc':<4} {'signs':>6} {'share':>7}")
    for key in sorted(strata):
        n = len(strata[key])
        print(f"{key[0]:<6} {key[1]:<11} {key[2]:<4} {n:>6} {n / len(signs):>7.1%}")
    print()

    sizes = {key: len(members) for key, members in strata.items()}
    alloc = allocate(sizes, args.size, args.min_per_stratum)

    rng = random.Random(args.seed)
    id_map = load_id_mapping()
    selected = []
    for key in sorted(strata):
        chosen = rng.sample(strata[key], alloc[key])
        weight = sizes[key] / alloc[key] if alloc[key] else 0
        selected += [("main", key, weight, s) for s in sorted(chosen, key=lambda s: s["sign_id"])]

    taken = {s["sign_id"] for _, _, _, s in selected}
    rest = [s for s in signs if s["sign_id"] not in taken]
    pilot = sorted(rng.sample(rest, min(args.pilot, len(rest))), key=lambda s: s["sign_id"])
    selected += [("pilot", stratum_of(s), 0, s) for s in pilot]

    rows = []
    for set_name, key, weight, sign in selected:
        ocr = sign.get("ocr_data", {})
        rows.append({
            "set": set_name,
            "ocr_id": sign["sign_id"],
            "id": id_map.get(sign["sign_id"], ""),
            "gloss": sign.get("spanish_word", ""),
            "source_batch_file": ocr.get("source_batch_file", ""),
            "source_page_ocr": ocr.get("source_page_ocr", ""),
            "sign_index_on_page": ocr.get("sign_index_on_page", ""),
            "hands": key[0],
            "components": key[1],
            "nmc": key[2],
            "stratum_size": sizes[key],
            "stratum_sample": alloc[key] if set_name == "main" else "",
            "weight": f"{weight:.3f}" if set_name == "main" else "",
            "ocr_confidence": ocr.get("ocr_confidence", ""),
            "visually_deduced_count": len(ocr.get("visually_deduced_fields", []) or []),
        })

    print(f"{'hands':<6} {'components':<11} {'nmc':<4} {'sampled':>8} {'weight':>8}")
    for key in sorted(strata):
        weight = sizes[key] / alloc[key] if alloc[key] else 0
        print(f"{key[0]:<6} {key[1]:<11} {key[2]:<4} {alloc[key]:>8} {weight:>8.2f}")
    print(f"\nSampled {len(rows) - len(pilot)} signs + {len(pilot)} pilot signs (seed {args.seed})")

    missing = sum(1 for r in rows if not r["id"])
    if id_map and missing:
        print(f"Warning: {missing} sampled signs have no current id in {ID_MAPPING_CSV}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
