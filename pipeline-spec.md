# pipeline-spec.md

## Overview

Six stages: collect → scrub → clean → categorise → store → analyse, plus a
presentation layer (dashboard) on top. Each stage reads from one location on
disk and writes to another — no stage reaches back upstream or mutates its own
input in place.

Everything below describes the pipeline **as built**. Where a decision was
open during design, the decision that was made is recorded here and the
reasoning lives in `decisions.md`.

**Two datasets run through the same code.** The private one (real exports,
entirely gitignored) and a tracked synthetic sample used for the public repo
and the deployed demo. Every path is environment-configurable (`config.py`),
which is what lets one pipeline serve both without a fork. See
*Synthetic vs. real* at the end.

---

## The refresh command

One command takes new bank exports through to an updated local dashboard:

```
.venv/bin/python refresh.py            # add --force to replace a same-day pull
```

It chains collect → clean → categorise → analyse → anomalies → export →
render, checking every precondition **before** the first stage so a bad run
stops rather than leaving half-updated outputs.

**Before running:** download the Account Activity CSV from each bank (both are
manual and login-gated — see sources.md) and leave them in `~/Downloads`. The
collectors find them by pattern: `Chase*_Activity_*.csv` and
`Discover-AllAvailable*.csv`. One export is enough; the other account keeps
whatever pulls are already in `raw/`. Override the search directory with
`SPEND_DOWNLOADS_DIR` if they live elsewhere.

**On success** it prints rows ingested per account, rows surviving cross-pull
dedupe, the Uncategorized count and dollar total with its share of spend, the
coverage date range (and whether it moved since the last refresh), and every
file written:

```
Ingested (newest pull per account, in raw/):
  chase        NNN data rows   chase_YYYY-MM-DD.csv  (new this run)
  discover     NNN data rows   discover_YYYY-MM-DD.csv  (existing)

After cross-pull dedupe:  N,NNN data rows → clean/transactions_clean.csv
Uncategorized:            NN rows, $N,NNN.NN (N.N% of $NN,NNN.NN spend)

Coverage:                 YYYY-MM-DD → YYYY-MM-DD  (N,NNN transactions)
  previously:             YYYY-MM-DD → YYYY-MM-DD  (N,NNN transactions)
```

Shape only — the figures are placeholders, since real output describes real
finances and is not reproduced in a tracked file. Note that "data rows"
excludes the header, while the collector prints its own count a few lines
earlier that *includes* it; the two differ by one on purpose.

That is enough to sanity-check a run at a glance: if the dedupe count is far
off the pull counts, or Uncategorized jumps, something changed upstream.

**Failure messages, and what each means:**

| Message | Cause | Fix |
|---|---|---|
| `categories.local.yaml is missing` | The personal rule overlay is absent. This is the dangerous one: without it the pipeline still exits 0, but a large share of rows falls to Uncategorized and every total is wrong. | Restore the file (it is gitignored and never in a clone). |
| `Python X.Y is too old` / `missing Python dependencies` | Run under the wrong interpreter. | `.venv/bin/python refresh.py`; recreate the venv from `requirements.txt` if needed. |
| `no new bank exports found in ~/Downloads` | Nothing matched either collector pattern. | Download the CSVs, or point `SPEND_DOWNLOADS_DIR` at where they are. |
| `no BLS benchmark workbook in raw/` | The benchmark the categorise and analyse stages compare against is missing. | `.venv/bin/python collect_bls.py` (manual download first — BLS blocks bots). |
| `already exists with different content today` | A pull for today already exists and the new export differs — refusing to clobber it. | Rerun with `--force` if the new export is the one you want. |
| `stage failed: <script>` | A stage exited non-zero; its output is printed above. | Fix the cause and rerun. Earlier stages already wrote, later ones did not. |

**Scope — this refreshes the LOCAL, real-data dashboard only.** It writes
`clean/`, `dashboard/data/metrics.json` and `analysis.local.md`, all
gitignored. It does not touch the public site. Updating that is a separate,
deliberate act: run `build_sample.py` (regenerates the synthetic sample and
the tracked `analysis.md`), then commit and push — Vercel rebuilds from the
committed sample and never sees real data.

---

## 1. Collect

- **Input:** Raw exports the user places in `~/Downloads` — Chase CSV,
  Discover CSV (manually downloaded from each bank's site), BLS CEX Excel
  file (manually downloaded via browser due to bot-blocking — see sources.md)
- **Output:** the file located and handed to Scrub; same-day idempotency is
  enforced here (a rerun that would replace a same-day pull with different
  content refuses unless `--force`)
- **Storage:** none of its own — collect and scrub are one step (below)
- **Tooling:** `collect_chase.py`, `collect_discover.py`, `collect_bls.py`,
  sharing `collect_common.py`. No automated fetch for any source: BLS blocks
  bots, and both banks require login.

## 2. Scrub

- **Input:** the raw CSV/XLSX from Collect (still containing account numbers,
  balances, etc.)
- **Output:** same file with sensitive columns dropped (Balance, Check or
  Slip #) and sensitive patterns redacted (account/card numbers, WEB IDs) by
  regex, applied to every cell rather than named columns
- **Storage:** `raw/<source>_<pull-date>.csv` — **`raw/` is gitignored and
  never committed.** The BLS workbook is copied byte-for-byte (`scrub=False`):
  it is public data, not a personal export.
- **Tooling:** `ingest.py`

## 3. Clean

- **Input:** scrubbed files in `raw/` (all pulls, not just the newest)
- **Output:** normalised transactions — merchant strings canonicalised,
  duplicate rows removed across overlapping pulls, signs normalised (Chase
  debits negative, Discover purchases positive → one convention: expenses
  positive), dates unified to ISO
- **Storage:** `clean/transactions_clean.csv` — **`clean/` is gitignored.**
  It holds real transaction rows and is never committed.
- **Tooling:** `clean.py` with `normalize.py`; rules in `categories.yaml`
  merged with the gitignored `categories.local.yaml` overlay

## 4. Categorise

- **Input:** `clean/transactions_clean.csv`
- **Output:** the same transactions mapped onto the BLS 14-category taxonomy,
  plus three admin buckets (Transfer, Income, Uncategorized) that are excluded
  from spend; a peer-payment review file; and the benchmark reconciliation
- **Storage:** `clean/transactions_categorized.csv` and
  `clean/zelle_review.csv` — both gitignored
- **Tooling:** `categorize.py`, resolving every row through the same
  `normalize.Resolver` the clean stage uses, so the merchant used for dedupe
  and the category assigned can never drift apart

## 5. Store

**Decision made: flat precomputed JSON, not SQLite.** The metric set is fixed
and small (seven questions), so a query engine buys nothing. Every number is
computed in Python and written once.

- **Input:** `clean/transactions_categorized.csv` + the BLS benchmark workbook
- **Output:** one JSON document holding every number the dashboard renders —
  one key per question (`q1_savings`…`q7_volatility`) plus a `meta` block
  (dataset flag, date range, row counts, per-month coverage, generation
  timestamp)
- **Storage:** `dashboard/data/metrics.json` (real, **gitignored**) or
  `dashboard/data/sample.metrics.json` (synthetic, **tracked** — the only file
  in `data/` that is). The directory is deny-by-default in
  `dashboard/.gitignore`, so anything new added there stays out of git.
- **Tooling:** `export_dashboard_data.py`, which imports the same
  `compute_metrics` / `compute_anomalies` functions the analyse stage prints
  from — no logic is duplicated between the report and the dashboard

## 6. Analyse

- **Input:** the categorised dataset (and, for Q5, the same rows scored)
- **Output:** answers to questions.md — savings rate and trend, 90-day budget
  drift, benchmark comparison, fixed/discretionary split, anomaly flags,
  volatility — as a printed report and as a written document
- **Storage:** `analysis.md` (**tracked**, rendered from the synthetic sample)
  and `analysis.local.md` (**gitignored**, rendered from real data). Both come
  from `render_analysis.py`, so neither is hand-maintained and neither can
  drift from its data.
- **Tooling:** `analyze.py` (Q1–Q4, Q7), `anomalies.py` (Q5),
  `render_analysis.py`. Q6 is a deliberate negative result: no forecast is
  produced, for reasons recorded in the analysis document.

## 7. Present

- **Input:** a metrics JSON — chosen by `METRICS_PATH`, **defaulting to the
  synthetic sample** so an unconfigured or misconfigured deploy cannot serve
  real data
- **Output:** a one-screen dashboard answering all seven questions
- **Tooling:** Next.js app in `dashboard/`. It renders the JSON and computes
  nothing; any new number a panel needs is added to the exporter, never
  derived in JavaScript.

```
cd dashboard && npm run dev                                  # synthetic sample
cd dashboard && METRICS_PATH=data/metrics.json npm run dev   # real, local only
```

---

## Synthetic vs. real

| | Real (private) | Synthetic (public) |
|---|---|---|
| Exports | `raw/` — gitignored | `sample/*.csv` — tracked |
| Rules overlay | `categories.local.yaml` — gitignored | `sample/categories.sample.yaml` — tracked |
| Intermediates | `clean/` — gitignored | `sample/clean/` — gitignored |
| Metrics | `dashboard/data/metrics.json` — gitignored | `dashboard/data/sample.metrics.json` — tracked |
| Analysis | `analysis.local.md` — gitignored | `analysis.md` — tracked |
| Built by | `refresh.py` | `build_sample.py` |

`config.py` reads every path from a `SPEND_*` environment variable with the
real pipeline as the default, which is what lets `build_sample.py` run the
identical code over `sample/` without any chance of touching real outputs.

## Decisions that were open during design, and how they resolved

- **Store stage: flat CSV vs. SQLite** → flat precomputed JSON (stage 5).
- **The format the dashboard reads** → `metrics.json`, and it is a contract:
  the UI renders it and computes nothing.
- **Whether BLS's manual download gets automated** → it stays a documented
  manual step. BLS serves an Akamai "Access Denied" page to scripted requests
  regardless of User-Agent; automating it would need their authenticated
  Public API, which is a separate access path and not worth it for an annual
  file.
