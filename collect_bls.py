"""
collect_bls.py — finds the latest BLS CE benchmark export in
~/Downloads and copies it into raw/ unscrubbed (it's public data).

Usage:
    python collect_bls.py [--force]

BLS blocks automated requests via Akamai bot protection (see the access
note in sources.md), so there is no automated fetch path — the file must
be downloaded manually through a browser. This script only looks for a
file already sitting in ~/Downloads.

The source is a binary .xlsx of public benchmark data, not a personal
transaction export, so it is copied byte-for-byte (scrub=False) — no
CSV parsing or cell-level regex is applied to it.

Scope note: this script does not deduplicate rows that overlap BETWEEN
pulls (e.g. a July pull and an August pull sharing late-July
transactions) — each pull writes its own date-tagged file, and
cross-pull dedup belongs in the clean stage (task 13). Proposed dedupe
key for task 13: (date, normalized_description, amount) — note this key
can collide on legitimate same-day identical charges, so task 13 needs
to decide whether to drop or keep those rather than assume. (This note
applies to the personal transaction sources; the BLS benchmark file
itself is a single annual table, not per-transaction rows.)
"""

import sys

from collect_common import collect, find_source

PATTERN = "reference-person-age-by-income-under-25*.xlsx"
SOURCE_NAME = "bls"


def main():
    force = "--force" in sys.argv[1:]

    source_path = find_source(PATTERN)
    if source_path is None:
        print(
            f"No file matching {PATTERN!r} found in ~/Downloads.\n"
            "BLS blocks automated requests (Akamai bot protection) — "
            "download the file manually via browser from "
            "https://www.bls.gov/cex/tables/cross-tab/mean/"
            "reference-person-age-by-income-under-25-2023-2024.xlsx "
            "and save it to ~/Downloads before rerunning "
            "(see the access note in sources.md)."
        )
        sys.exit(1)

    collect(source_path, SOURCE_NAME, scrub=False, force=force)


if __name__ == "__main__":
    main()
