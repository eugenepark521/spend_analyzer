"""
ingest.py — pulls a source file into raw/, scrubbing account/card numbers
on the way in. Run once per source.

Usage:
    python ingest.py <source_file> <source_name>

Example:
    python ingest.py ~/Downloads/Chase_Activity.csv chase
    python ingest.py ~/Downloads/Discover-AllAvailable.csv discover
"""

import re
import csv
import sys
from pathlib import Path
from datetime import date

# Patterns that look like account/card numbers or bank-assigned reference
# IDs. Applied to every cell, not just specific columns, so nothing slips
# through in a description field.
PATTERNS = [
    (re.compile(r"\b\d{12,19}\b"), "[REDACTED-NUM]"),          # card/account-length digit runs
    (re.compile(r"(?i)ending in\s*\d{2,4}"), "ending in [XXXX]"),  # "ending in 1234"
    (re.compile(r"(?i)web id:?\s*\d+"), "WEB ID: [REDACTED]"),  # ACH web IDs
    (re.compile(r"(?i)acct(?:ount)?[#:\s]*\d{4,}"), "acct [REDACTED]"),
]

# Whole columns to drop outright, regardless of source file — these aren't
# "sensitive patterns" a regex can catch, they're columns that just
# shouldn't exist downstream at all (case-insensitive, matched by header name).
DROP_COLUMNS = {"balance", "check or slip #", "check number"}


def scrub_cell(value: str) -> str:
    for pattern, replacement in PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def ingest_file(source_path: Path, source_name: str, scrub: bool = True) -> Path:
    raw_dir = Path("raw")
    raw_dir.mkdir(exist_ok=True)

    pull_date = date.today().isoformat()
    out_path = raw_dir / f"{source_name}_{pull_date}{source_path.suffix}"

    if not scrub:
        out_path.write_bytes(source_path.read_bytes())
        print(f"Wrote unscrubbed copy to {out_path}")
        return out_path

    with open(source_path, "r", encoding="utf-8", errors="replace", newline="") as f_in:
        reader = csv.reader(f_in)
        rows = list(reader)

    if not rows:
        print("Source file is empty — nothing to write.")
        sys.exit(1)

    header = rows[0]
    keep_indexes = [
        i for i, col in enumerate(header)
        if col.strip().lower() not in DROP_COLUMNS
    ]
    dropped = [col for col in header if col.strip().lower() in DROP_COLUMNS]

    with open(out_path, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        for row in rows:
            kept_row = [row[i] for i in keep_indexes if i < len(row)]
            scrubbed_row = [scrub_cell(cell) for cell in kept_row]
            writer.writerow(scrubbed_row)

    print(f"Wrote scrubbed copy to {out_path}")
    if dropped:
        print(f"Dropped columns entirely: {dropped}")
    print("Reminder: raw/ and *.csv are gitignored — this file will not be committed.")
    return out_path


def main():
    if len(sys.argv) != 3:
        print("Usage: python ingest.py <source_file> <source_name>")
        sys.exit(1)

    source_path = Path(sys.argv[1]).expanduser()
    source_name = sys.argv[2]

    if not source_path.exists():
        print(f"File not found: {source_path}")
        sys.exit(1)

    ingest_file(source_path, source_name)


if __name__ == "__main__":
    main()
