# Spend Analyzer

Takes raw bank exports, cleans and categorises them onto the **BLS Consumer
Expenditure Survey** taxonomy, and compares spending shares against comparable
households. It answers a fixed set of questions ([`questions.md`](questions.md))
on one screen — savings rate, budget drift, benchmark comparison,
fixed-vs-discretionary split, anomalies, volatility, and one deliberate
non-answer.

> **The tracked dataset and the live dashboard are synthetic.** Every
> transaction, merchant, counterparty, amount and date in this repo is
> invented by [`sample/make_sample_data.py`](sample/make_sample_data.py). No
> real financial data is committed here or served publicly.

**Live dashboard →** https://spend-analyzer-zeta.vercel.app

Why it exists and what was decided: [`BRIEF.md`](BRIEF.md).

---

## Run it

A fresh clone runs end-to-end on the synthetic data — no credentials, no
accounts, nothing to configure.

```bash
git clone https://github.com/eugenepark521/spend_analyzer.git
cd spend_analyzer

python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_sample.py          # regenerates sample data + metrics + analysis.md

cd dashboard && npm install && npm run dev # → http://localhost:3000
```

`build_sample.py` runs the real pipeline over `sample/`, so the demo is a
genuine end-to-end proof rather than a fixture that can drift from the code.

## The two modes

|  | Synthetic (default) | Real (author only) |
|---|---|---|
| Exports | `sample/*.csv` — tracked | `raw/` — gitignored |
| Rule overlay | `sample/categories.sample.yaml` — tracked | `categories.local.yaml` — gitignored |
| Metrics | `dashboard/data/sample.metrics.json` — tracked | `dashboard/data/metrics.json` — gitignored |
| Analysis | `analysis.md` — tracked | `analysis.local.md` — gitignored |
| Built by | `build_sample.py` | `refresh.py` |

Every path is read from a `SPEND_*` environment variable ([`config.py`](config.py))
with the real pipeline as the default, which is what lets one codebase serve
both without a fork. The dashboard's `METRICS_PATH` inverts that — it
**defaults to the synthetic file**, so an unconfigured or misconfigured deploy
cannot serve real finances.

Refreshing the real, local dashboard from new exports is one command
(`refresh.py`); its preconditions, output and failure messages are documented
in [`pipeline-spec.md`](pipeline-spec.md#the-refresh-command).

## The pipeline

| Stage | Does | Script |
|---|---|---|
| 1. Collect | Finds the newest export in `~/Downloads`; refuses to clobber a same-day pull that differs | `collect_chase.py`, `collect_discover.py`, `collect_bls.py` |
| 2. Scrub | Drops balance columns, redacts account/card numbers and web IDs from every cell | `ingest.py` |
| 3. Clean | Canonicalises merchants, dedupes across overlapping pulls, normalises signs and dates | `clean.py` + `normalize.py` |
| 4. Categorise | Maps onto the BLS 14 plus three admin buckets; writes a peer-payment review file | `categorize.py` |
| 5. Store | Computes every dashboard number once into a flat JSON contract | `export_dashboard_data.py` |
| 6. Analyse | Answers the seven questions; scores anomalies; renders the document | `analyze.py`, `anomalies.py`, `render_analysis.py` |
| 7. Present | One-screen dashboard that renders the JSON and computes nothing | `dashboard/` (Next.js) |

Full stage-by-stage detail, storage locations and git status:
[`pipeline-spec.md`](pipeline-spec.md). Judgement calls and their reasoning:
[`decisions.md`](decisions.md).

---

## Adding a new account or data source

### A third card or bank

Genuinely pluggable — no code changes:

- **A collector.** Copy `collect_chase.py`, change `PATTERN` (the
  `~/Downloads` filename glob) and `SOURCE_NAME`. The shared logic in
  `collect_common.py` handles same-day idempotency and backup/restore.
- **Merchant rules.** Add entries to the `merchants:` list in
  `categories.yaml` (or the gitignored overlay for anything identifying).
  First match wins; ordering is the only precedence mechanism.
- **The dedupe key already handles it.** It is
  `(account, date, merchant, amount)` — `account` is part of the key
  specifically so a same-day, same-amount purchase at the same merchant on two
  cards doesn't falsely collapse. A new account needs nothing here.
- **Declare the sign convention.** Add the account to `sources:` in
  `categories.yaml`, saying whether an outgoing amount is `negative` or
  `positive` in that issuer's own export. Everything downstream — the amount
  normalisation and the peer-payment direction — reads this one declaration.
  An undeclared account raises rather than defaulting, because the two
  possible answers are both self-consistent and one silently inverts every
  total for that account.
- **Document the schema** in [`sources.md`](sources.md): columns, date format,
  and the category column if the issuer supplies one.

Needs code changes — the pipeline currently hardcodes two sources:

- **A loader** in `clean.py`. `load_chase()` and `load_discover()` each map
  one issuer's columns onto the internal schema. Add `load_<name>()`, register
  it in the `pulls` dict, and relax the "must have both accounts" guard.
- **Issuer-supplied categories.** The `discover_fallback:` map applies only
  when `source == "discover"`. A second issuer with its own category column
  needs its own map and a branch to read it.
- **`refresh.py`'s `SOURCES` dict**, so the new account is preflighted and
  collected with the others.

### A different benchmark

The benchmark loader (`categorize.py:load_benchmark`) locates the BLS
cross-tab column by its header label and asserts one row per category. Another
survey would need a new loader, but the contract it returns is small —
`{category: annual_mean}` plus a total — and everything downstream consumes
only that. **The 14 category names themselves are load-bearing**: a rule
assigning any name outside the BLS 14 plus the three admin buckets fails an
assertion at load. Swapping taxonomies is a bigger change than swapping
benchmarks.

### A manual CSV

Cheapest path: shape it into one of the existing raw schemas and drop it in
`raw/` (or `sample/`) with the right filename prefix. `clean.py` globs
`<account>_*.csv`, so anything matching an existing loader's schema is picked
up without touching code.

---

## What the data cannot tell you

Read this before trusting any number on the dashboard. These are properties of
the source data, not bugs — most of them cannot be fixed by better code.

**Cash is invisible.** ATM withdrawals are recorded as `Uncategorized`, not
guessed at, because what the cash was spent on genuinely isn't in the data.
Cash deposits are treated as funding rather than income. Every dollar
withdrawn and spent is a hole in every category total.

**Only two accounts exist here.** Anything paid another way — a third card,
someone else paying, a bank not covered — simply isn't in the dataset. The
totals are "what passed through these two accounts", not "what was spent".

**Alcohol, tobacco and reading are floors, not totals.** They're only visible
when the merchant is a dedicated store. Wine inside a restaurant bill or a
supermarket shop is invisible, so those categories are undercounts by
construction and shouldn't be compared to the benchmark at face value.

**Two different kinds of date are mixed.** Chase exports a posting date;
Discover exports a transaction date. Day-level analysis therefore compares
things that can differ by a day or two. Monthly aggregates are mostly immune;
anything finer is not.

**Peer-to-peer payments rarely say what they bought.** A Zelle or Venmo
description names a person, not a purchase. Those rows land on a documented
default category, so a real bucket of spending sits under a label that was
assumed rather than observed. They're written to a review file precisely
because hand-tagging them matters more than any other refinement.

**The benchmark is a cohort average, not a peer.** BLS reports the mean of a
demographic cell. Comparing one household to it says "different from the
average of this group", which is not the same as "unusual". No individual
household looks like an average.

**The benchmark's income filter is a proxy, not a match.** BLS's "income
before taxes" measures *earned* income, so a household funded substantially by
transfers, aid or loan proceeds is not what the bracket describes, even when
its spending power is similar.

**Below-benchmark total spend has two explanations and the data can't
separate them.** Either spending really is lower, or capture is incomplete
(see cash, above). Both produce the same number.

**The anomaly detector's precision is untested.** Every flag it has produced
has been a legitimate large payment — rent, tuition — because the dataset
contains no known errors to catch. A detector that has never caught a real
error has an unknown false-positive rate and a completely unmeasured
false-negative rate. Treat flags as a review queue, not findings. Its
documented failure modes are in [`analysis.md`](analysis.md#what-would-make-it-wrong).

**Uncategorized is a real number, not a gap to close.** It's a deliberate
refusal to guess: identifiable merchants whose goods are unknowable, plus
untagged peer payments. Forcing it to zero would mean inventing categories
from amounts, which is false precision.

---

## What I'd build next

Roughly in order of what would most improve the numbers per unit of effort.

1. **Hand-tag the largest peer payments.** The biggest single source of
   miscategorised real spending, and it needs no code — just working down
   `clean/zelle_review.csv` into overlay rules. Highest value, lowest effort.
2. **Give the anomaly detector something to detect.** Inject known synthetic
   errors — duplicate charges, an inflated amount, a subscription that
   silently doubles — and measure precision and recall. Until then, "0 flagged"
   and "2 flagged" are equally uninformative about whether it works.
3. **Split the peer default by counterparty history** rather than a single
   Miscellaneous default. A counterparty who has always been rent is not the
   same as one who has always been dinner, and that's inferable from the rows
   already present.
4. **Automate the BLS pull.** Currently manual because the site blocks
   scripted requests regardless of User-Agent. Their authenticated Public API
   is a separate access path — worth it only if the benchmark starts changing
   more than annually.
5. **A store-stage rethink, if the metric set stops being fixed.** Flat JSON
   is right for seven known questions. Ad-hoc querying would justify SQLite;
   nothing today does.
6. **Reconcile against statement balances.** The pipeline asserts a lot about
   individual rows but never checks that the set of rows sums to what the bank
   says the balance did. That would catch whole classes of silent capture gaps
   — including some of the cash problem above.

Deliberately not planned: bank API integration (no free path for these
issuers), and forecasting (rejected with reasoning in
[`analysis.md`](analysis.md#why-this-over-forecasting)).
