import argparse
import csv
import glob
import os
import re
import subprocess
import sys
from collections import defaultdict

DEFAULT_BACKUP_DIR = os.path.expanduser(
    "~/Documents/GitHub/LSA_MorphDict-RawOCR-Private/data/processed"
)
OUTPUT_DIR = "work/raw_ocr_history"
BATCH_PATH = "data/processed/{name}"
SCAN_SUBJECT = re.compile(r"new (raw )?processed data|re-scan|new json files|reprocessed files", re.IGNORECASE)


def is_scan(event):
    _, _, subject, status, _ = event
    return status in "AR" or (status == "M" and SCAN_SUBJECT.search(subject) is not None)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def batch_history(path):
    out = git("log", "--all", "--reverse", "--format=C\t%H\t%ad\t%s", "--date=short",
              "--raw", "--no-abbrev", "--", path)
    events, current = [], None
    for line in out.splitlines():
        if line.startswith("C\t"):
            _, sha, date, subject = line.split("\t", 3)
            current = (sha, date, subject)
        elif line.startswith(":") and current:
            meta = line.split("\t", 1)[0].split()
            events.append((*current, meta[4][0], meta[3]))
    return events


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR, help="folder with the backed-up lote_*.json files")
    parser.add_argument("--export-first", metavar="DIR", help="write the first committed version of each batch here")
    args = parser.parse_args()

    backup_files = sorted(glob.glob(os.path.join(args.backup_dir, "lote_*.json")))
    if not backup_files:
        sys.exit(f"No lote_*.json files found in {args.backup_dir}")

    batch_rows, commit_batches, commit_info = [], defaultdict(set), {}
    unmatched = []
    for backup in backup_files:
        name = os.path.basename(backup)
        backup_blob = git("hash-object", backup).strip()
        events = batch_history(BATCH_PATH.format(name=name))

        snapshot_idx = next((i for i, e in enumerate(events) if e[4] == backup_blob and e[3] != "D"), None)
        if snapshot_idx is None:
            unmatched.append(name)
            continue
        first_idx = max(i for i, e in enumerate(events[:snapshot_idx + 1]) if is_scan(e))
        edits = [e for e in events[first_idx + 1:snapshot_idx + 1] if e[3] == "M"]

        for sha, date, subject, _, _ in edits:
            commit_batches[sha].add(name)
            commit_info[sha] = (date, subject)

        first = events[first_idx]
        batch_rows.append({
            "batch": name,
            "first_commit": first[0][:7],
            "first_date": first[1],
            "first_subject": first[2],
            "snapshot_commit": events[snapshot_idx][0][:7],
            "snapshot_date": events[snapshot_idx][1],
            "edits": len(edits),
            "edit_commits": "; ".join(f"{e[0][:7]} {e[1]} {e[2]}" for e in edits),
        })

        if args.export_first:
            os.makedirs(args.export_first, exist_ok=True)
            content = subprocess.run(["git", "cat-file", "-p", first[4]], capture_output=True, check=True).stdout
            with open(os.path.join(args.export_first, name), "wb") as f:
                f.write(content)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    write_csv(os.path.join(OUTPUT_DIR, "per_batch.csv"), batch_rows)
    commit_rows = [
        {"commit": sha[:7], "date": commit_info[sha][0], "batches": len(batches), "subject": commit_info[sha][1]}
        for sha, batches in sorted(commit_batches.items(), key=lambda kv: commit_info[kv[0]][0])
    ]
    if commit_rows:
        write_csv(os.path.join(OUTPUT_DIR, "per_commit.csv"), commit_rows)

    untouched = sum(1 for r in batch_rows if r["edits"] == 0)
    print(f"Backup files: {len(backup_files)}; matched in git history: {len(batch_rows)}; unmatched: {len(unmatched)} {unmatched}")
    print(f"Batches identical to their first commit: {untouched}")
    print(f"Batches edited after their first commit: {len(batch_rows) - untouched}\n")
    print(f"{'date':<11} {'commit':<8} {'batches':>7}  subject")
    for row in commit_rows:
        print(f"{row['date']:<11} {row['commit']:<8} {row['batches']:>7}  {row['subject'][:90]}")
    print(f"\nWritten to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
