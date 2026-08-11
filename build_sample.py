"""
build_sample.py — runs the FULL pipeline against the tracked synthetic sample
and writes dashboard/data/sample.metrics.json (tracked, deployed by Vercel).

The sample metrics are generated, never hand-written: the dashboard's demo is
therefore a real proof the pipeline runs end to end, not a fixture that could
drift away from what the code does.

Every stage runs as a subprocess with SPEND_* env vars pointing at sample
locations, so nothing here can touch the real clean/ CSVs or the real
metrics.json — and SPEND_CATEGORIES_LOCAL redirects the personal rule overlay
to sample/categories.sample.yaml, so no real name is ever loaded.

Run: .venv/bin/python build_sample.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample"
WORK = SAMPLE / "clean"                      # sample intermediates (gitignored)
OUT = ROOT / "dashboard" / "data" / "sample.metrics.json"

ENV = {
    **os.environ,
    "SPEND_RAW_DIR": str(SAMPLE),
    "SPEND_BENCH_DIR": str(SAMPLE),          # public-domain BLS copy lives here
    "SPEND_CLEAN_DIR": str(WORK),
    "SPEND_CATEGORIES_LOCAL": str(SAMPLE / "categories.sample.yaml"),
    "SPEND_METRICS_OUT": str(OUT),
    "SPEND_DATASET": "sample",
}
STAGES = ["sample/make_sample_data.py", "clean.py", "categorize.py",
          "analyze.py", "anomalies.py", "export_dashboard_data.py"]
# The tracked analysis.md is rendered from the sample metrics, so the document
# in the repo is reproducible rather than hand-maintained. The real one is
# rendered locally to the gitignored analysis.local.md:
#   .venv/bin/python render_analysis.py \
#       --metrics dashboard/data/metrics.json --out analysis.local.md
RENDER = ["render_analysis.py", "--metrics", str(OUT), "--out", "analysis.md"]


def ensure_benchmark():
    """The BLS workbook is a public-domain US government work product, so a
    copy is tracked in sample/ — that makes the sample reproducible from a
    fresh clone without the gitignored raw/.

    The filename is copied VERBATIM. The dashboard publishes it as the
    benchmark's provenance, and the benchmark really is that file pulled on
    that date; renaming it to sit inside the sample's invented timeline would
    put a date the workbook never had on the one line whose job is to say
    where the number came from. Only the transactions are synthetic."""
    if list(SAMPLE.glob("bls_*.xlsx")):
        return
    src = sorted((ROOT / "raw").glob("bls_*.xlsx"))
    if not src:
        sys.exit("No BLS workbook in sample/ or raw/ — see sources.md (manual download).")
    shutil.copy2(src[-1], SAMPLE / src[-1].name)
    print(f"Copied benchmark {src[-1].name} -> sample/ (public domain, name kept)")


def main():
    ensure_benchmark()
    WORK.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        print(f"\n=== {stage} ===")
        r = subprocess.run([sys.executable, stage], env=ENV, cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stdout.write(r.stdout)
            sys.stderr.write(r.stderr)
            sys.exit(f"{stage} failed")
        # Stage reports are long; show the lines that prove the stage worked.
        tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-6:]
        print("\n".join(tail))

    print("\n=== render_analysis.py ===")
    r = subprocess.run([sys.executable, *RENDER], env=ENV, cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit("render_analysis.py failed")
    print(r.stdout.strip())
    print(f"\nWrote {OUT.relative_to(ROOT)} and analysis.md")


if __name__ == "__main__":
    main()
