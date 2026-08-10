# pipeline-spec.md

## Overview
Six stages: collect → scrub → clean → categorise → store → analyse.
Each stage reads from one location on disk and writes to another —
no stage reaches back upstream or mutates its own input in place.

---

## 1. Collect
- **Input:** Raw exports the user places in `~/Downloads` — Chase CSV,
  Discover CSV (manually downloaded from each bank's site), BLS CEX
  Excel file (manually downloaded via browser due to bot-blocking —
  see sources.md access note)
- **Output:** Untouched copies, unscrubbed
- **Storage:** *(not persisted separately — collection and scrub happen
  as one step in the current implementation; see Scrub below)*
- **Tooling:** Manual browser download (no automated fetch for any
  source currently — BLS blocks bots; bank sites require login)

## 2. Scrub
- **Input:** Raw CSV/XLSX files from Collect (still containing account
  numbers, balances, etc.)
- **Output:** Same file, with sensitive columns dropped (Balance, Check
  or Slip #) and sensitive patterns redacted (account/card numbers,
  WEB IDs) via regex
- **Storage:** `raw/<source>_<pull-date>.csv` (e.g. `raw/chase_2026-07-29.csv`)
  — `raw/` is gitignored, never committed
- **Tooling:** `ingest.py` (built in task 8)

## 3. Clean
- **Input:** Scrubbed files in `raw/`
- **Output:** Normalized transactions — merchant strings standardized
  (e.g. "SQ *BLUE BOTTLE #4417" and "BLUEBOTTLE COFFEE" merged),
  duplicate rows removed across overlapping statement periods, signs
  normalized (Chase: debit negative; Discover: purchase positive —
  both converted to a single consistent convention), currency/date
  formats unified
- **Storage:** `clean/transactions_clean.csv` (single combined file
  across both accounts) — NOT gitignored once real scrubbing is
  confirmed reliable, but reassess before committing any real data
- **Tooling:** to be built in task 13

## 4. Categorise
- **Input:** `clean/transactions_clean.csv`
- **Output:** Same transactions, each mapped onto the BLS 14-category
  taxonomy (per the mapping table in sources.md), using Discover's
  existing categories where usable and merchant-string rules for
  Chase's uncategorized rows
- **Storage:** `clean/transactions_categorized.csv`
- **Tooling:** to be built in task 13, using the first-pass mapping
  already drafted in sources.md as the starting rule set

## 5. Store
- **Input:** `clean/transactions_categorized.csv` plus the BLS benchmark
  file (`raw/bls_cex_under25_income0-15k.xlsx`)
- **Output:** A single queryable dataset joining personal spend and
  benchmark data on the shared category taxonomy
- **Storage:** `clean/store.csv` or a lightweight local SQLite file
  (`clean/finance.db`) — decision TBD in task 13 based on how the
  analysis stage ends up querying it
- **Tooling:** pandas for now; SQLite only if query complexity in
  task 14 justifies it

## 6. Analyse
- **Input:** The stored dataset from Store
- **Output:** Answers to questions.md — savings rate trend, category
  drift, benchmark comparison, anomaly flags, forecast — written to
  `analysis.md`, plus whatever numeric outputs the dashboard (task 18)
  will read from
- **Storage:** `analysis.md` (findings) + intermediate output files
  the dashboard consumes (format TBD in task 18)
- **Tooling:** pandas + whichever modelling approach is chosen in
  task 15 (forecast vs. anomaly detection)

---

## Known open decisions (to resolve while building, not before)
- Store stage: flat CSV vs. SQLite — deferred to task 13
- Exact output format the dashboard reads from — deferred to task 18
- Whether BLS's manual-download requirement gets solved with API auth
  or stays a documented manual step — deferred to task 20 (one-command
  refresh)
