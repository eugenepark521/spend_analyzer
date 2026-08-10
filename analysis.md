# analysis.md — task 14: answers to questions.md

Computed from `clean/transactions_categorized.csv` by `analyze.py` (run it to
reproduce every number). Data coverage: full calendar months 2024-10 through
2026-06 (21 months — a month counts as full only if it lies strictly inside
both accounts' own coverage windows; Chase starts 2024-07-29, Discover
2024-09-17, so 2024-08/09 are excluded as partial); 2026-07 is partial
(through 07-28) and excluded from monthly series. The trailing 6 full months
(2026-01..2026-06) are all well populated, so 6-month questions are answered;
"income" throughout means the pipeline's Income category (payroll, FAFSA
disbursements, marketplace payouts, family support — see sources.md caveat
that this is not BLS-sense earned income).

## 1. Savings rate and 6-month trend

A month-by-month savings-rate series is not meaningful in this data — income
arrives in lumps (FAFSA, quarterly transfers), so single full months range
from +86% to −2,392% (Feb 2026 income was $76.22) — so the honest answer is
aggregate: trailing 6 full months (2026-01..06) savings rate is **−61.8%**
(income $12,129.22, spend $19,621.24), down sharply from **+46.0%** over the
prior 6 months (2025-07..12), i.e. trending strongly down.

## 2. Category drift from budget, trailing 90 days

Against the $1,000/month total budget (pro-rated to $2,956.88 for the 90-day
window 2026-04-30..2026-07-28), actual spend was **$14,108.72 — $11,151.84
over** — and since the budget is a single monthly total with no per-category
targets, "drift by category" here means share of that overage: **Education
$6,917.26 (62.0%)**, **Housing $2,824.24 (25.3%)**, **Apparel and services
$1,782.37 (16.0%)** are the top three contributors.

## 3. Category split vs. BLS benchmark

Reusing the task-13 reconciliation (full-history spend vs. the under-25,
<$15k-income BLS CEX cell): I am **above** benchmark share in Apparel and
services (+9.0pp, 12.4% vs 3.4%), Miscellaneous (+3.8pp), Education (+3.1pp),
Entertainment (+1.5pp), and Food (+1.0pp), and **below** in Housing (−11.3pp)
and Transportation (−6.8pp), with 6.9% of my spend sitting in Uncategorized,
which has no BLS counterpart.

## 4. Fixed vs. discretionary spend vs. benchmark

Defining fixed = Housing + Healthcare + Personal insurance and pensions +
Education (a judgement call: committed obligations; everything else, including
Uncategorized, counts as discretionary), my split is **49.9% fixed / 50.1%
discretionary** ($18,011.90 of $36,097.70) versus the benchmark household's
**62.8% fixed / 37.2% discretionary** ($15,733 of $25,041).

## 5. Anomalous transactions this month

Zero of July 2026's 94 spend transactions cross the |3.5| modified-z flag
threshold (method and full results in the Modelling section below); the top
scorer is the known-legitimate $800 rent Zelle to L. at +3.27.

## 6. Forecasted next-month spend and error range

No forecast is produced: forecasting was considered as task 15's method and
rejected — ~24 monthly observations, structurally lumpy top categories, and
a mid-series regime change make a category-level monthly model unfittable
and unvalidatable (full reasoning in the Modelling section below).

## 7. Category volatility, month-over-month

Over the trailing 6 full months (2026-01..06), the highest month-over-month
volatility (coefficient of variation of monthly totals, categories averaging
≥$50/month) is **Miscellaneous (CV 4.06)**, **Education (1.80)**,
Uncategorized (1.21), Entertainment (1.13), and Apparel and services (0.97) —
and volatility is **falling**, not rising, in every category comparable to the
prior 6 months (Education 2.27→1.80, Entertainment 1.31→1.13, Apparel
1.19→0.97, Housing 1.20→0.46, Food 0.77→0.45; Miscellaneous and Uncategorized
have no prior-window figure, their averages were under $50/month).

# Modelling (task 15): anomaly detection

Implemented in `anomalies.py`; run it to reproduce every number below.

## Method

Each spend transaction in the scored month gets a modified z-score
(Iglewicz–Hoaglin) on its log1p-transformed amount, M = 0.6745 ×
(x − median) / MAD, flagged at |M| ≥ 3.5. The scored month is the calendar
month of the newest transaction (here July 2026) and the baseline is the
trailing 12 full months before it (2025-07-01..2026-06-30, 496 rows), both
derived from the data at run time. Scoring population is spend rows (14 BLS
categories + Uncategorized) with amount > 0 — refunds and credits are
excluded because the log transform needs positives and "unusual refund" is a
different question. Baselines are per-category where the category has ≥ 30
baseline transactions (Food n=170, Miscellaneous n=107, Apparel and services
n=66, Entertainment n=63); all other categories, plus Uncategorized always
(a mixed bag by construction — deliberately unknowable merchants and untagged
peer rows — so "unusual for Uncategorized" is not meaningful), score against
the pooled global baseline of all 496 rows; a category whose MAD is zero is
rescored globally.

## Why this over forecasting

A next-month category-level forecast was rejected because the data cannot
support one: only ~24 monthly observations exist (two seasonal cycles — far
too few to fit, let alone validate, a seasonal model); the two largest
categories are structurally lumpy rather than monthly-recurring (Education,
24.7% of spend, is semester-driven tuition; Housing runs partly through
irregular peer payments); and the series contains a regime change — the data
is US-based until a move to Japan in June 2026 (123 of 127 Japan-linked
rows fall in June–July 2026; Japan-side spend is 60% of July; the data ends
2026-07-28 mid-stay, so trip vs. relocation is not distinguishable) — so a model
fit on the full history would span two different spending regimes. Anomaly
detection instead uses ~1,188 transaction-level observations, and the regime
change becomes a documented finding to inspect flags against, not a
confound baked silently into a forecast.

## What would make it wrong

- **Thin categories inherit the wrong yardstick**: Housing and Education
  fall below the n≥30 minimum, so their rows score against the global pool —
  their scores mean "large for any transaction of mine", not "large for
  rent/tuition", which is why routine tuition flags retrospectively.
- **The regime change is only half-handled**: the baseline is ~92% US-regime
  while the scored month is 60% Japan-side, so Japan-typical small purchases
  read as "unusually small" (the −2.2..−2.7 scores below are konbini items
  and FX fees, an artifact, not a finding); a bigger-spending trip would
  have produced false high-side flags the same way.
- **Symmetry assumption**: MAD scoring treats log-amounts as roughly
  symmetric, but within-category log-spend is still right-skewed, so
  low-side scores compress and the detector is effectively one-sided in
  practice (nothing can realistically cross −3.5).
- **Statistically extreme ≠ wrong**: a legitimate one-time large purchase is
  indistinguishable from an erroneous or fraudulent one — every retrospective
  flag (tuition ×2, rent) is a legitimate payment, so flags are a review
  queue, not verdicts.
- **Judgment-set constants**: n≥30, the 3.5 cutoff, the 12-month window, and
  log1p are conventions, not derived values, and results are sensitive to
  them — the $800 rent Zelle at +3.27 would flag at a cutoff of 3.25.

## Results

July 2026: **0 of 94 transactions flag at |M| ≥ 3.5**. The top scores, on
inspection, are all explainable: the $800 rent Zelle to L. (+3.27,
global model — legitimate, already hand-tagged Housing via
transaction_overrides), two large vintage-clothing purchases from the Japan
trip's Shimokitazawa cluster (Furugi Popup $541.93 at +2.90, Noill $497.22
at +2.85, both scored against their own Apparel baseline — real purchases
consistent with the trip pattern), and on the low side small Japan-regime
rows (¥-denominated konbini items and sub-$1 FX fees at −2.2..−2.7 — the
regime artifact noted above, not real anomalies). Retrospectively
self-scoring the baseline year flags 3 of 496 rows — UC Davis tuition
$6,917.26 (+5.01) and $2,418.00 (+4.16) and Arlington Farm rent $1,600.00
(+3.83) — confirming the threshold fires on genuine extremes, but also that
to date every flag is a legitimate lumpy payment, not an error: the method
is working as designed, and this month shows no evidence of true anomalies.
