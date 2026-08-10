# decisions.md — judgement calls made across the pipeline

## Task 18: the two store/output decisions pipeline-spec.md left open

- **Store stage: flat precomputed JSON, not SQLite.** The dashboard's metric
  set is fixed and small (seven questions), so a query engine buys nothing —
  every number is precomputed in Python by `export_dashboard_data.py` (which
  imports the same `compute_metrics`/`compute_anomalies` functions that
  `analyze.py`/`anomalies.py` print from, so no logic is duplicated) and
  written to `dashboard/data/metrics.json`. Revisit only if a future task
  needs ad-hoc querying rather than fixed metrics.
- **`metrics.json` is the dashboard's contract with the pipeline.** One key
  per question (`q1_savings`..`q7_volatility`) plus `meta` (date range, row
  counts, per-month coverage, generation timestamp). The UI renders this file
  and computes nothing; any new number a panel needs is added to the exporter,
  never derived in JavaScript. The dashboard reads the file path from the
  `METRICS_PATH` env var (default: the real `data/metrics.json`), so task 19
  can point the deployed app at a synthetic sample file as a config change,
  not a refactor.

## 2026-08-10: personal matching rules moved to categories.local.yaml

Tracked files now contain no identifiable counterparty names (initials only in
docs/comments). The three rule blocks that must match real names or real
transaction details — the family-support Zelle income pattern, the H.P. peer
override, and all transaction_overrides — live in `categories.local.yaml`
(gitignored), which `normalize.Resolver` merges at load by appending local
list sections after the tracked ones. Without the file the pipeline still
runs; those rows just fall back to the peer Miscellaneous default. Verified
byte-identical pipeline output before/after the move.

# Judgement calls made in the clean + categorise stage (task 13)

Everything below is implemented in `clean.py`, `categorize.py`, `normalize.py`
and the rules file `categories.yaml`. Where a call was a coin-flip, the
reasoning is spelled out so it can be reversed by editing `categories.yaml`
without touching code.

## 0. The missing 2026-07-29 pulls were recreated

`raw/` was supposed to contain two pulls each of Chase and Discover
(2026-07-29 and 2026-07-30) as the dedupe test case, but the 07-29 files were
absent when this task started. The original exports were still in
`~/Downloads` (`Chase0399_Activity_20260729.csv`,
`Discover-AllAvailable-20260728.csv`), so I re-ran them through the project's
own `ingest.py` (identical scrubbing) and renamed the outputs to the 07-29
pull date. The recreated files are **byte-identical** (same SHA-256) to the
07-30 pulls, which is exactly the "same underlying export pulled on different
days" fixture the task describes. Nothing was deleted.

## 1. Merchant normalisation

- The raw description is never modified; the canonical name lives in a new
  `merchant` column next to `description_raw`.
- Two layers:
  1. **Junk stripping** (`normalize.strip_junk`) removes payment-processor
     noise before any matching: `APPLE PAY ending in [XXXX]`, redaction
     tokens from ingest, FX conversion tails (`5680.00 @ 0.0061788 JPY`,
     `Yen 536 X 0.006194 (EXCHG RTE)`), `WEB/PPD/CCD ID` references, Stripe
     `ST-…` payout refs, trailing `MM/DD` dates (including glued forms like
     `06/26KATSUSHIK`), phone numbers, and digit runs ≥5 (store numbers,
     register/receipt IDs).
  2. **Canonicalisation**: an ordered regex rule list in `categories.yaml`
     maps cleaned descriptions to a canonical merchant (`SQ *DAVIS CREAMERY…`
     and `SQ *DAVIS CREAMERY Davis CA 0001…` → `DAVIS CREAMERY`; Chase
     `PP*SPOTIFYUSAI` and Discover `SPOTIFY P3…` → `SPOTIFY`). Rows matching
     no rule fall back to a generic cleaner that strips processor prefixes
     (`SQ *`, `TST*`, `DD *`, `PP*`, `SP `, `SPO*`, `PY *`, `CTLP*`,
     `CASH APP*`, `PAYPAL *`, …) and trailing city/state/ward tokens from a
     curated list.
- Zelle rows canonicalise to `ZELLE <counterparty>`; the counterparty is
  parsed from the **raw** description (junk stripping would eat phone-number
  counterparties), dropping exactly one trailing bank reference token
  (`JPM99…`, `BAC…`, `WFCT…`, 11-digit refs). Phone-number counterparties are
  kept as the identity (`ZELLE 714…9177`, masked here).
- Result on this data: **950 distinct raw descriptions → 337 canonical
  merchants** (top-20 collapse groups printed by `clean.py`).
- Caveat: `Zelle payment to E.` (nickname form) and `Zelle payment from E. Y.`
  (full-name form) remain distinct counterparties (`ZELLE E.` vs
  `ZELLE E. Y.`) — merging nickname vs full-name identities felt riskier than
  leaving them split.

## 2. Dedupe across overlapping pulls

- Key: **(account, date, canonical merchant, normalised amount)**. The task
  specified `(date, merchant, amount)`; `account` is added because pulls only
  ever overlap within one bank — without it, a same-day same-amount purchase
  at the same merchant on both cards would falsely collapse.
- **Within-file duplicates are preserved**: if a key appears N times in one
  pull, all N are kept (each row gets a rank 0..N-1 within its pull; dedupe
  keeps, per (key, rank) slot, the row from the latest pull). Final
  multiplicity per key = max multiplicity seen in any single pull.
  Verified on real cases: the two same-day $5.00 SPIN scooter rides, the two
  same-day $10.93 ANYS TACOS charges, and the CLICKUP double-charge
  (2 × −$29 on consecutive days plus 4 reversal rows) all survive intact.
- Test case asserted in `clean.py`: Chase 668+668 rows → 668; Discover
  520+520 → 520. The script fails loudly if dedupe doesn't collapse back to
  the single-pull count.

## 3. Sign, currency, dates

- Convention: **expenses positive, income/credits negative.** Chase (debits
  negative) is flipped; Discover (purchases positive) is kept.
- Chase's `Details` DEBIT/CREDIT flag is **not authoritative**: 4 merchant
  refunds are flagged DEBIT with positive amounts. The sign of `Amount` is
  trusted instead; `clean.py` asserts only that CREDIT rows are never
  negative and prints a note about the refund rows.
- Dates unified to ISO `YYYY-MM-DD`. Discover: transaction date is canonical
  (`date`), posting date kept in `post_date`. Chase exports a single date
  which is a **posting** date; it fills both columns rather than leaving
  `post_date` empty — flagged here so the analysis stage knows Chase dates
  can lag the actual transaction by a day or two.
- Currency: no currency column exists in either export; both are
  USD-denominated. `clean.py` asserts every amount parses as a number **and**
  cross-checks all 120 foreign-currency rows: the description embeds
  `foreign_amount × rate`, and the product must reproduce the USD amount
  within $0.02. All 120 reconcile, proving `Amount` is already converted USD.

## 4. Taxonomy: the 14 BLS categories + three admin buckets

Spend categories are exactly the BLS 14 (validated at load time — a rule
assigning any other name fails an assertion). Three non-BLS admin buckets
exist, none of which enter the benchmark comparison:

- **Transfer** — excluded from spend, kept for balance reconciliation.
- **Income** — payroll (ChipGril, Naya Dessert Cafe, Target, Handshake AI),
  FAFSA/financial-aid disbursements (`UNIVERSITY OF C STUDENT FE`), and
  Depop/Grailed seller payouts. The task did not name this bucket, but these
  rows are neither spending nor account-to-account transfers; mapping them to
  any BLS category would wrongly net spend down, and calling them "Transfer"
  would corrupt balance reconciliation. Deliberate addition — flagged here.
- **Uncategorized** — no guessing; counted in spend totals as unattributed
  outflow, reported separately.

## 5. Transfers vs peer payments — how they were told apart

**Transfer** (excluded) = money moving between my own accounts or paying my
own card, identifiable structurally:
- `INTERNET PAYMENT - THANK YOU` / `RETURNED INTERNET PMT` (Discover card
  payments and a bounced payment),
- `DISCOVER E-PAYMENT` (the same payments seen from the Chase side),
- `Online Transfer to/from CHK …0750` (own checking accounts, Chase Type
  ACCT_XFER),
- `ACCTVERIFY` / `Yardi Penny Test` micro-deposits,
- `ATM CASH DEPOSIT` (cash entering the account is funding, not income),
- Discover cashback redemptions (`CASHBACK BONUS REDEMPTION`, `APPLE PAY
  STMT CRDT REDEMPTION`) — treated as non-spend rather than negative spend,
  since a statement credit isn't tied to any category.

**Peer payment** (included in spend) = a named human/phone counterparty on a
P2P rail: Chase Types QUICKPAY_DEBIT / CHASE_TO_PARTNERFI (outgoing) and
QUICKPAY_CREDIT / PARTNERFI_TO_CHASE (incoming), plus Venmo, Wise, and Apple
Cash rows (see §6). The distinguishing test: transfers move money between
accounts *I* own or settle *my own* card; peer payments have a counterparty
who isn't me.

## 6. Peer payments

- Included in spend per the task rationale (reimbursements for real
  consumption). Outgoing positive; incoming negative, netting spend down.
- Direction comes from the source sign, cross-checked against the Chase Type
  and the `to`/`from` wording; any conflict → direction `ambiguous`, row left
  Uncategorized. (Zero conflicts in this data.)
- Default category **Miscellaneous**; the only seeded override is
  `ZELLE EASTERN BAKERY INC → Food` (the counterparty names a bakery).
  Further hand-tags belong in `peer.overrides` in `categories.yaml`.
- **Venmo, Wise, and Apple Cash are treated as peer payments**, not
  transfers: money leaves the tracked accounts into P2P/stored-value rails
  whose spending never appears in these exports, so excluding them would
  undercount. This includes Apple Cash *top-ups* (outgoing) and Apple Cash →
  bank transfers (incoming, netting back). All land in `zelle_review.csv`.
- All 266 peer rows are in `clean/zelle_review.csv`, sorted by |amount|.
  **Warning worth reading:** incoming ($13,480.56) far exceeds outgoing
  ($5,081.84), so the Miscellaneous bucket nets to **−$8,404.72** and shows
  as negative in the category table. Large incoming Zelle (e.g. C.L.
  $1–2k monthly, R.O.'s many repayments) may actually be rent-share or
  income-like flows rather than "repaying me for consumption" — hand-tagging
  the big rows in the review file matters more than any other refinement.

## 7. Category calls that follow BLS definitions but look surprising

- **Laundromats** (WASH LAUNDRY, CSC ServiceWorks) → *Apparel and services*
  (BLS puts laundry/dry-cleaning there, not Housing).
- **USPS / FedEx** → *Housing* (BLS: postage & stationery under housekeeping).
- **Hotels** (Toggle Hotel Tokyo) → *Housing* (BLS: "other lodging").
- **Cellular / eSIM** (Ubigi/Transatel) → *Housing* (BLS: telephone services
  under utilities).
- **Sports betting** (PrizePicks, Underdog incl. ViaTrustly deposits, Dabble)
  → *Entertainment*, with payouts (the `REAL TIME PAYMENT … FROM:
  PrizePicks/Underdog` credits) as negative Entertainment, so the category
  nets to true gambling loss — matching BLS's net-loss treatment.
- **Tuition refund** (`UC DAVIS TUITIONREF` +$2,418) → negative *Education*,
  offsetting the tuition charge it reverses (not Income).

## 8. Other merchant judgement calls

- **Amazon** → Miscellaneous. No item detail exists; Discover files it under
  Merchandise. Guessing Apparel vs household vs anything else seemed worse
  than a documented Miscellaneous default.
- **Target, Walmart, Costco** → Food. Discover itself categorises Target as
  Supermarkets; these are grocery-dominant for this cardholder. Documented
  assumption, easily re-ruled.
- **7-Eleven** → Food everywhere, including the one row Discover calls
  Gasoline (amounts there are snack-sized; merchant rules outrank the
  Discover fallback).
- **`tandem-ck-arf WEB PMTS`** → Housing: recurring −$800 monthly plus
  utility-sized odd amounts; "ARF" matches Arlington Farm (Davis apartments),
  corroborated by the Yardi penny test and Discover's `YSI*ARLINGTON FARM`
  (YSI = Yardi payment portal), also mapped to Housing.
- **Shimokitazawa/Setagaya square merchants** (FURUGIPOPUP, BIG TIME, NOILL,
  AYNE, DYLAN SOUTH SIDE, USHIROMAE, ONE LEFT, AGEM) → Apparel and services:
  "furugi" literally means used clothing, Big Time is a known vintage chain,
  and the cluster (same ward, same trip, clothing-sized ¥ amounts) makes
  vintage-shopping the coherent reading. This is the least certain block of
  rules — it moves ≈$1.4k into Apparel.
- **Discover miscategorisations corrected by rules**: UCD MU GAMES AREA
  (Education → Entertainment), MONARCH FUN ZONE (Medical Services →
  Entertainment), restaurants filed under Merchandise (Pho Oishii, Eggdrop,
  Tamagoken, Shinpachi, Present Coffee, Utts Cafe, Upper Crust, Pita Kabob →
  Food), UCD STORES MBS-MARKET (snacks → Food) vs MBS MAIN (bookstore →
  Education).
- **Discover refunds inside "Payments and Credits"** (Depop, Target, Zara,
  Uber Eats, Poppin, SP-brand returns) are matched by merchant rules *after*
  the two true card-payment patterns, so they net against their real
  category instead of vanishing into Transfer.
- **ATM cash withdrawals** → Uncategorized (real spending, unknowable
  category — no guessing), while ATM cash *deposits* → Transfer. Asymmetric
  on purpose: withdrawn cash is presumed consumed, deposited cash is funding.
- **Apple subscriptions** (`APPLE.COM/BILL`) → Entertainment (iCloud/app
  subscriptions); **Spotify** → Entertainment; **ClickUp, Anthropic/Claude**
  → Miscellaneous (software tools, not clearly Education).
- **Deliberately Uncategorized** (identifiable merchant, unknowable goods):
  33MM Studio (largest at $805.50 + $235 − $155.77 refund), SQ *San Rafael,
  TikTok Shop, Taobao, Mercari, eBay, AkiraCribs (PayPal), Glamstar (PayPal),
  SS Ayase/Machiya (Tokyo, ¥24k — possibly capsule hotel/spa), Queen (Tokyo),
  Victoria (Tokyo), the Tokyo malls (Hikarie, Tokyu Plaza, Coredo), Popcorn
  Home Shopping, Raspberry Roach, Athens West, PBC Sacramento, Hugo's, LGB
  Travel, MyPlots. These surface in the categorize.py top-20 report for
  hand-tagging.
- **Fees** (Chase FX adjustment fees, non-Chase ATM fees) → Miscellaneous.
- **C.L. Zelles** (mom — rent support, 15 rows, $10.2k) → Income via
  `income_patterns`, so they're excluded from spend entirely instead of
  netting spend down through the peer Miscellaneous default. Side effect:
  income-path rows take the generic merchant, so BAC/JPM bank refs that the
  peer path would have stripped survive in the merchant column for these
  rows (cosmetic only; income is excluded from spend and dedupe is
  unaffected since the refs are stable across pulls).
- **H.P. Zelle** ($120, 2025-01-02) → Transportation via
  `peer.overrides` (Uber ride reimbursement).
- **Transaction overrides** (`transaction_overrides` in categories.yaml,
  matched after income, before peer detection): hand-tags for single rows
  identified by exact (date, |amount|) — currently three Zelle rent payments
  (L. $800 + $81, A. $325 → Housing). Amount matches on absolute
  value so the spend-positive yaml values work against Chase's negative raw
  amounts. The override forces only the *category*; peer rows keep their
  merchant/counterparty/direction, so dedupe keys in clean.py and
  zelle_review.csv membership are unaffected. A (date, amount) collision
  with an unrelated same-day row would mis-tag it — checked at add time
  (these three dates have no other row at the same amount).

## 9. Reconciliation findings (2026-08-05 run)

- **Zero-dollar BLS categories.** Healthcare, Cash contributions, and Personal
  insurance and pensions all show $0 in my data. This is plausible rather than
  a pipeline gap: as a student I'm likely still covered under a parent's health
  insurance, don't make independent cash contributions (e.g. charitable giving,
  support to other households), and don't have my own insurance/pension
  payments. Noting this explicitly so it reads as a finding, not a missing
  category.
- **Total spend vs. benchmark.** My annualized total spend ($17,958) is about
  72% of the BLS benchmark average ($25,041) for the under-25, <$15k income
  cohort. Two categories account for most of the divergence in the other
  direction: Apparel and services (11.9% vs. 3.4%) and Education (24.8% vs.
  21.6%), both consistent with being a student. I have not independently
  verified whether the lower total reflects genuinely lower spending or
  incomplete capture (e.g. cash transactions not passing through Chase/
  Discover). Flagging as an open question rather than resolving it here.
- **Uncategorized total.** $2,507 (7% of spend) remains Uncategorized,
  consisting of deliberately-unknowable merchants (per the merchants: rules
  in categories.yaml) plus untagged small peer-to-peer payments where the
  transaction description gives no indication of what was purchased. This
  was a deliberate choice over guessing categories from amount alone, which
  would introduce false precision.

## 10. Known limitations

- Chase dates are posting dates (see §3) — same-merchant dedupe across banks
  is unaffected (key includes account), but day-level analysis mixes
  transaction dates (Discover) with posting dates (Chase).
- The benchmark's income filter (<$15k earned income) is a proxy, not a
  match, for FAFSA-funded reality — already flagged in sources.md.
- Alcohol/Tobacco/Reading are only visible when the merchant is a dedicated
  store (liquor store, smoke shop, bookstore); alcohol inside restaurant and
  supermarket bills is invisible, so those categories are floors, not totals.
