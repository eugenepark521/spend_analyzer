# sources.md

## (a) Personal transaction exports

### Chase (checking + card activity)
- Export path: manually downloaded from secure.chase.com →
  Download Account Activity → CSV, saved to ~/Downloads
- Columns: Details, Posting Date, Description, Amount, Type
  (Balance column present in raw export; stripped before use — not needed downstream)
- Date format: MM/DD/YYYY, single date column (Posting Date)
- Sign convention: debits (purchases, transfers out, fees) are negative;
  credits (deposits, incoming transfers) are positive
- Type values observed: DEBIT_CARD, CHASE_TO_PARTNERFI, FEE_TRANSACTION,
  QUICKPAY_DEBIT, ACH_CREDIT, ACH_DEBIT
- History available: roughly two years, ending at the pull date

### Discover (card activity)
- Export path: manually downloaded from discover.com →
  Download Account Activity → CSV, saved to ~/Downloads
- Columns: Trans. Date, Post Date, Description, Amount, Category
- Date format: MM/DD/YYYY, two date columns (transaction vs. posting date,
  can differ by 1+ days)
- Sign convention: purchases are positive; payments/credits are negative
  — OPPOSITE of Chase. This must be normalized in task 13 before the two
  sources can be combined.
- Category column is pre-populated by Discover (Restaurants, Merchandise,
  Travel/Entertainment, Services, Education, Payments and Credits, etc.)
  — a useful head start for the taxonomy in part (c), but needs mapping
  onto whatever taxonomy is chosen since it won't match BLS categories directly
- History available: roughly two years, ending at the pull date. This
  account's history starts some weeks LATER than the other's, so the two
  coverage windows do not align — the analysis stage therefore treats a month
  as "full" only when it lies strictly inside both accounts' windows, and
  excludes the partial months at either end.

## (b) Benchmark

### US BLS Consumer Expenditure Survey (CE) — Age of reference person
### by income before taxes, Under 25 bracket
- URL: https://www.bls.gov/cex/tables/cross-tab/mean/
  reference-person-age-by-income-under-25-2023-2024.xlsx
  (parent page: https://www.bls.gov/cex/tables.htm#crosstab)
- Filter applied: Age of reference person = Under 25;
  Income before taxes = lowest published bracket (~$0–15,000)
- Format: Excel (.xlsx), direct download, no API/auth needed
- Update frequency: Annual, published as a 2-year rolling mean.
  Current file covers 2023–2024. Historical tables back to 1986.
- Licence: U.S. government work product — public domain
  (bls.gov/bls/linksite.htm)
- Contents: mean annual expenditure, % share of total spend, and
  standard error across BLS's 14 major expenditure categories, for
  consumer units matching the age × income filter above
- Caveat: the lowest income bracket is used as the closest available proxy
  for a low-cash-inflow young adult, not because it is a precise income
  match. BLS's "income before taxes" measures *earned* income, so any inflow
  that is not earnings — transfers, aid, loan proceeds — is invisible to the
  bracket while still funding real spending. The benchmark is therefore a
  reference cohort, not a claim of equivalence. Flagged here so it is not a
  surprise in the analysis stage.
  
### Access note (found in task 8)
BLS blocks automated requests (curl, scripts) via Akamai bot protection —
returns an "Access Denied" HTML page instead of the file, even with a
browser-like User-Agent header. The file must be downloaded manually
through an actual browser. This means task 12's collection script cannot
fully automate the benchmark pull; it will need either BLS's official
Public API (a separate, authenticated access path) or a documented manual
refresh step.

## (c) Category taxonomy

### Source: BLS Consumer Expenditure Survey major categories
- URL: https://www.bls.gov/cex/csxgloss.htm (category definitions/glossary)
  and https://www.bls.gov/cex/tables.htm (where the 14 categories appear
  as column headers in every table)
- Format: defined in HTML glossary + used as column headers across all
  CE Excel tables
- Update frequency: category definitions are stable; BLS revises the
  schema only rarely (most recent structural change predates 2012 data)
- Licence: U.S. government work product — public domain

### The 14 target categories
Food · Alcoholic beverages · Housing · Apparel and services ·
Transportation · Healthcare · Entertainment · Personal care products
and services · Reading · Education · Tobacco products and smoking
supplies · Miscellaneous · Cash contributions · Personal insurance
and pensions

### First-pass mapping (own categories → BLS category)

| My source category               | Maps to (BLS)                                                 | Notes |
|-----------------------------------|----------------------------------------------------------------|-------|
| Discover: Restaurants             | Food                                                            | BLS "Food" includes food away from home |
| Discover: Merchandise             | *split* — Apparel and services, Entertainment, Miscellaneous  | Too coarse as-is; needs manual sub-classification per merchant in task 13 |
| Discover: Travel/ Entertainment   | Entertainment                                                   | — |
| Discover: Services                | *split* — Personal care products and services, Miscellaneous  | Depends what the service is (e.g. eyebrow threading vs. FedEx shipping) |
| Discover: Education               | Education                                                       | — |
| Discover: Payments and Credits    | *excluded from spend analysis*                                 | These are payments to the card, not spending — must be filtered out before category totals, not mapped |
| Chase: DEBIT_CARD                 | *split by merchant*                                             | Chase gives no category at all — every DEBIT_CARD row needs merchant-string classification in task 13 |
| Chase: CHASE_TO_PARTNERFI (Zelle) | *excluded or Cash contributions*                                | Peer-to-peer transfers aren't retail spend; classify as gifts/cash contributions only if clearly a gift, otherwise exclude |
| Chase: FEE_TRANSACTION            | Miscellaneous                                                   | Foreign exchange fees, etc. |
| Chase: ACH_CREDIT / ACH_DEBIT     | *excluded* — transfers, not spend                              | |
| Chase: QUICKPAY_DEBIT             | *split* — same as Zelle logic                                  | |

### Known gaps, to resolve in task 13
- Discover's "Merchandise" and "Services" buckets are too broad to map
  1:1 — will need per-merchant rules (e.g. regex on description strings)
  to split them into BLS's finer categories
- Chase provides zero categorization — every transaction needs
  classification from the raw description
- Neither source distinguishes Alcoholic beverages, Tobacco, Reading,
  or Personal insurance and pensions as separate line items — these
  will likely be near-zero or absorbed into Miscellaneous/Food unless
  individual merchants can be identified
- Zelle/QuickPay peer transfers are ambiguous by nature — no automated
  rule can tell "paying back a friend for dinner" from "gift" from
  "rent split." Task 13 will need either manual tagging or a documented
  default assumption
