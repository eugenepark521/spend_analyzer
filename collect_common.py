"""
collect_common.py — shared glob-lookup and same-day idempotency logic
used by collect_chase.py, collect_discover.py, and collect_bls.py.

ingest_file() (in ingest.py) always writes its target unconditionally —
that's its existing, unchanged contract. The idempotency behaviour lives
here instead: collect() backs up any existing target, lets ingest_file()
write a fresh copy, then compares hashes. If they match, the backup is
dropped (no-op). If they differ, the backup is restored unless --force
was given, so a same-day rerun never silently clobbers a same-day
re-export.
"""

import hashlib
import sys
from datetime import date
from pathlib import Path

from ingest import dest_path, ingest_file

DOWNLOADS = Path("~/Downloads").expanduser()


def find_source(pattern: str) -> Path | None:
    matches = sorted(
        DOWNLOADS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not matches:
        return None
    if len(matches) > 1:
        print(
            f"Multiple files matched {pattern!r} in ~/Downloads; "
            f"using most recently modified: {matches[0].name}"
        )
    return matches[0]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return sum(1 for _ in f)


def collect(source_path: Path, source_name: str, scrub: bool, force: bool) -> None:
    # Ask ingest where the file will land rather than recomputing it here —
    # two copies of this path could disagree and back up the wrong file.
    target = dest_path(source_name, source_path.suffix)

    existed_before = target.exists()
    backup = None
    old_size = None
    old_hash = None
    if existed_before:
        old_size = target.stat().st_size
        old_hash = sha256_of(target)
        backup = target.with_name(target.name + ".bak")
        target.rename(backup)

    out_path = ingest_file(source_path, source_name, scrub=scrub)
    new_hash = sha256_of(out_path)
    new_size = out_path.stat().st_size

    if not existed_before:
        if scrub:
            print(f"run: wrote {out_path}, rows={count_rows(out_path)}, sha256={new_hash}")
        else:
            print(f"run: wrote {out_path}, bytes={new_size}, sha256={new_hash}")
        return

    if new_hash == old_hash:
        backup.unlink()
        print(f"{target.name}: already current, skipping")
        return

    if force:
        backup.unlink()
        print(f"{target.name}: content changed, --force given, replaced "
              f"(old bytes={old_size}, new bytes={new_size}).")
        return

    if scrub:
        old_rows = count_rows(backup)
        new_rows = count_rows(out_path)
        out_path.unlink()
        backup.rename(target)
        print(f"WARNING: {target.name} already exists with different content today "
              f"(existing rows={old_rows}, new rows={new_rows}). "
              f"Re-run with --force to replace.")
    else:
        out_path.unlink()
        backup.rename(target)
        print(f"WARNING: {target.name} already exists with different content today "
              f"(existing bytes={old_size}, new bytes={new_size}). "
              f"Re-run with --force to replace.")
    sys.exit(1)
