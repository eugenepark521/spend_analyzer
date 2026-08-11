"""
config.py — where each pipeline stage reads and writes.

Defaults are the real personal pipeline (raw/ -> clean/ -> dashboard/data/
metrics.json). Every path is overridable by environment variable so the same
code can run against the tracked synthetic sample (see build_sample.py) with
no edits and no risk of overwriting real outputs.
"""

import os
from pathlib import Path

# Scrubbed bank exports in (clean.py globs <account>_*.csv here).
RAW_DIR = Path(os.environ.get("SPEND_RAW_DIR", "raw"))

# Where the BLS benchmark workbook lives (bls_*.xlsx, newest wins).
BENCH_DIR = Path(os.environ.get("SPEND_BENCH_DIR", str(RAW_DIR)))

# Intermediate CSVs written by clean.py and categorize.py.
CLEAN_DIR = Path(os.environ.get("SPEND_CLEAN_DIR", "clean"))

# Personal matching rules merged over categories.yaml. Unset => the gitignored
# categories.local.yaml beside categories.yaml; set => that file instead.
CATEGORIES_LOCAL = os.environ.get("SPEND_CATEGORIES_LOCAL")

# Where export_dashboard_data.py writes, and what it stamps meta.dataset with.
METRICS_OUT = Path(os.environ.get("SPEND_METRICS_OUT", "dashboard/data/metrics.json"))
DATASET = os.environ.get("SPEND_DATASET", "personal")
