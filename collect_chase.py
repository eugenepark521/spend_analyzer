"""
collect_chase.py — finds the latest Chase account activity export in
~/Downloads and ingests it into raw/ (scrubbed).

Usage:
    python collect_chase.py [--force]

Chase requires a manual, login-gated export — there is no automated
fetch path (see sources.md). This script only looks for a file already
sitting in ~/Downloads.

Scope note: this script does not deduplicate rows that overlap BETWEEN
pulls (e.g. a July pull and an August pull sharing late-July
transactions) — each pull writes its own date-tagged file, and
cross-pull dedup belongs in the clean stage (task 13). Proposed dedupe
key for task 13: (date, normalized_description, amount) — note this key
can collide on legitimate same-day identical charges, so task 13 needs
to decide whether to drop or keep those rather than assume.
"""

import sys

from collect_common import collect, find_source

PATTERN = "Chase*_Activity_*.csv"
SOURCE_NAME = "chase"


def main():
    force = "--force" in sys.argv[1:]

    source_path = find_source(PATTERN)
    if source_path is None:
        print(
            f"No file matching {PATTERN!r} found in ~/Downloads.\n"
            "Chase requires a manual login-gated export — download the "
            "Account Activity CSV from secure.chase.com and save it to "
            "~/Downloads before rerunning (see sources.md)."
        )
        sys.exit(1)

    collect(source_path, SOURCE_NAME, scrub=True, force=force)


if __name__ == "__main__":
    main()
