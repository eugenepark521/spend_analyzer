"""
refresh.py — one command: new bank exports -> updated LOCAL dashboard.

    .venv/bin/python refresh.py [--force]

Chains the stages that already exist (collect -> clean -> categorise ->
analyse -> anomalies -> export -> render) so a refresh is one invocation
rather than eight remembered ones.

SCOPE — this updates the PRIVATE, real-data dashboard on this machine only.
It writes clean/, dashboard/data/metrics.json and analysis.local.md, all of
which are gitignored. It does NOT touch the public site: that serves the
synthetic sample, is rebuilt by `build_sample.py`, and only changes when a
commit is pushed. The two are deliberately separate and this script never
crosses between them.

Everything is checked BEFORE any stage runs, so a bad precondition stops the
run instead of leaving half-updated outputs behind.
"""

# Annotations stay unevaluated so this file still *parses and runs* on an
# older interpreter — otherwise `Path | None` raises a TypeError at import and
# the reader gets a traceback instead of the dependency message below.
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_RULES = ROOT / "categories.local.yaml"
RAW = ROOT / "raw"
CLEAN = ROOT / "clean"
METRICS = ROOT / "dashboard" / "data" / "metrics.json"
ANALYSIS_LOCAL = ROOT / "analysis.local.md"
DOWNLOADS = Path(os.environ.get("SPEND_DOWNLOADS_DIR", "~/Downloads")).expanduser()

# account -> (collector script, ~/Downloads glob) — the patterns the
# collectors themselves use, repeated here only to preflight them.
SOURCES = {
    "chase": ("collect_chase.py", "Chase*_Activity_*.csv"),
    "discover": ("collect_discover.py", "Discover-AllAvailable*.csv"),
}
REQUIRED_MODULES = {"pandas": "pandas", "yaml": "PyYAML", "openpyxl": "openpyxl"}


def die(headline: str, *detail: str) -> "None":
    sys.stdout.flush()   # keep the error after the progress lines, not before
    print(f"\nREFRESH STOPPED: {headline}", file=sys.stderr)
    for line in detail:
        print(f"  {line}", file=sys.stderr)
    sys.exit(1)


def rows_in(path: Path) -> int:
    """Data rows in a CSV (header excluded). Deliberately not
    collect_common.count_rows, which counts every line including the header —
    both appear in one run's output, so the summary says "data rows"."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return max(sum(1 for _ in f) - 1, 0)


def newest_pull(account: str) -> Path | None:
    pulls = sorted(RAW.glob(f"{account}_*.csv"))
    return pulls[-1] if pulls else None


def preflight() -> dict:
    """Every reason this run could produce wrong or partial output, checked
    before the first stage. Returns the sources found in ~/Downloads."""
    # 1. The personal rule overlay. Without it the pipeline does NOT crash —
    #    it quietly resolves several hundred rows to Uncategorized and every
    #    downstream number silently changes. That failure is invisible in the
    #    output, so it has to be caught here.
    if not LOCAL_RULES.exists():
        die(f"{LOCAL_RULES.name} is missing.",
            f"Expected at: {LOCAL_RULES}",
            "It holds the personal matching rules — real merchant rules, the",
            "income patterns naming employers/institutions, the peer-counterparty",
            "overrides, the exact (date, amount) hand-tags, and the local place",
            "tokens. It is gitignored on purpose and is NOT in a fresh clone.",
            "",
            "Without it the pipeline still runs and still exits 0, but a large",
            "share of rows falls through to Uncategorized and every total, share",
            "and benchmark comparison is wrong. Restore it before refreshing.")

    # 2. Interpreter is new enough, and has the pipeline's dependencies.
    if sys.version_info < (3, 10):
        die(f"Python {sys.version_info.major}.{sys.version_info.minor} is too old.",
            f"Running under: {sys.executable}",
            "The pipeline needs 3.10+. Use the project venv:",
            "    .venv/bin/python refresh.py")
    missing = [pkg for mod, pkg in REQUIRED_MODULES.items()
               if importlib.util.find_spec(mod) is None]
    if missing:
        die("missing Python dependencies: " + ", ".join(missing),
            f"Running under: {sys.executable}",
            "Use the project venv, which has them installed:",
            "    .venv/bin/python refresh.py",
            "If the venv itself is missing or broken, recreate it:",
            "    python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt")

    # 3. At least one new export to ingest. One is enough — the other account
    #    keeps whatever pulls are already in raw/ — but zero means there is
    #    nothing to refresh FROM.
    found = {}
    for account, (_, pattern) in SOURCES.items():
        matches = sorted(DOWNLOADS.glob(pattern),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            found[account] = matches[0]
    if not found:
        die("no new bank exports found in ~/Downloads.",
            f"Looked in: {DOWNLOADS}",
            *[f"  {account}: {pattern}" for account, (_, pattern) in SOURCES.items()],
            "",
            "Both banks require a manual, login-gated download (see sources.md).",
            "Save the Account Activity CSV(s) to ~/Downloads and rerun.")

    # 4. The BLS benchmark, needed by the categorise and analyse stages.
    if not list(RAW.glob("bls_*.xlsx")):
        die("no BLS benchmark workbook in raw/.",
            f"Looked for: {RAW}/bls_*.xlsx",
            "BLS blocks automated download (see sources.md's access note), so",
            "fetch it manually and run:  .venv/bin/python collect_bls.py")

    # 5. A same-day re-export that differs from what was already ingested is
    #    handled by collect_common (it refuses and asks for --force). Warn
    #    here so the reason is visible before the stage prints it.
    today = date.today().isoformat()
    for account in found:
        existing = RAW / f"{account}_{today}.csv"
        if existing.exists():
            print(f"note: {existing.name} already exists — if the new export "
                  f"differs, the collector will refuse unless --force is given.")
    return found


def snapshot() -> dict:
    """What the outputs looked like before this run, so the summary can show
    what actually changed rather than just what exists."""
    prev = {}
    if METRICS.exists():
        try:
            m = json.loads(METRICS.read_text())
            prev["range"] = (m["meta"]["date_range"]["start"],
                             m["meta"]["date_range"]["end"])
            prev["rows"] = m["meta"]["rows"]
        except Exception:
            pass
    return prev


def run(args: list[str], label: str) -> str:
    print(f"  → {label}")
    r = subprocess.run([sys.executable, *args], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        die(f"stage failed: {' '.join(args)}",
            "The output above is from the failing stage. Nothing after it ran,",
            "so clean/ and dashboard/data/metrics.json may be from the previous",
            "refresh — fix the cause and rerun.")
    return r.stdout


def summarise(prev: dict, collected: dict) -> None:
    print("\n" + "=" * 68)
    print("REFRESH COMPLETE — local, real-data dashboard")
    print("=" * 68)

    print("\nIngested (newest pull per account, in raw/):")
    for account in sorted(SOURCES):
        pull = newest_pull(account)
        if pull is None:
            print(f"  {account:9} — no pulls present")
            continue
        note = "new this run" if account in collected else "existing"
        # "data rows" is explicit because the collector prints its own count a
        # few lines above INCLUDING the header, so a bare "rows" here would
        # look like the two disagreed by one.
        print(f"  {account:9} {rows_in(pull):>6,} data rows   {pull.name}  ({note})")

    clean_csv = CLEAN / "transactions_clean.csv"
    cat_csv = CLEAN / "transactions_categorized.csv"
    if clean_csv.exists():
        print(f"\nAfter cross-pull dedupe:  {rows_in(clean_csv):,} data rows "
              f"→ {clean_csv.relative_to(ROOT)}")

    if cat_csv.exists():
        unc_n, unc_total, spend_total = 0, 0.0, 0.0
        with open(cat_csv, newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                if row.get("in_spend", "").strip().lower() == "true":
                    amt = float(row["amount"] or 0)
                    spend_total += amt
                    if row["category"] == "Uncategorized":
                        unc_n += 1
                        unc_total += amt
        share = (100 * unc_total / spend_total) if spend_total else 0.0
        print(f"Uncategorized:            {unc_n:,} rows, ${unc_total:,.2f} "
              f"({share:.1f}% of ${spend_total:,.2f} spend)")

    if METRICS.exists():
        m = json.loads(METRICS.read_text())
        rng = (m["meta"]["date_range"]["start"], m["meta"]["date_range"]["end"])
        rows = m["meta"]["rows"]
        line = f"\nCoverage:                 {rng[0]} → {rng[1]}  ({rows:,} transactions)"
        if prev.get("range") and prev["range"] != rng:
            line += f"\n  previously:             {prev['range'][0]} → {prev['range'][1]}"
            line += f"  ({prev.get('rows', 0):,} transactions)"
        elif prev.get("range") == rng:
            line += "\n  (unchanged from the previous refresh — no new dates arrived)"
        print(line)

    print("\nWrote:")
    for p in (clean_csv, cat_csv, CLEAN / "zelle_review.csv", METRICS, ANALYSIS_LOCAL):
        if p.exists():
            print(f"  {p.relative_to(ROOT)}")

    print("\nSee the refreshed dashboard:")
    print("  cd dashboard && METRICS_PATH=data/metrics.json npm run dev")
    print("\nThis updated LOCAL data only. All of the files above are gitignored.")
    print("The public site still serves the synthetic sample — to change that,")
    print("run build_sample.py, then commit and push; Vercel rebuilds from the")
    print("committed sample, never from real data.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Refresh the local real-data dashboard from new bank exports.")
    ap.add_argument("--force", action="store_true",
                    help="replace a same-day pull whose content differs")
    a = ap.parse_args()

    print("Preflight…")
    collected = preflight()
    prev = snapshot()

    print(f"\nCollecting ({', '.join(sorted(collected))}):")
    for account in sorted(collected):
        script = SOURCES[account][0]
        out = run([script, *(["--force"] if a.force else [])], f"{script}")
        for line in out.splitlines():
            if line.strip():
                print(f"      {line}")

    print("\nRunning pipeline:")
    for stage in ("clean.py", "categorize.py", "analyze.py", "anomalies.py",
                  "export_dashboard_data.py"):
        run([stage], stage)
    run(["render_analysis.py", "--metrics", str(METRICS),
         "--out", str(ANALYSIS_LOCAL)], "render_analysis.py → analysis.local.md")

    summarise(prev, collected)


if __name__ == "__main__":
    main()
