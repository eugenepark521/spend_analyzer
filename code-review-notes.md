# Code review findings (/code-review high, 2026-08-07)

## categories.yaml

### line 60 — CONFIRMED
Income pattern '^WWW\.GRAILED\.COM\s+WWW\.GRAILE' matches Grailed card PURCHASES, not just seller payouts, misclassifying real spend as Income

Failure scenario: Confirmed in clean/transactions_categorized.csv: Chase DEBIT_CARD purchases on 2026-02-23 (-$61.18) and 2026-04-02 (-$146.10) are tagged Income (matched_rule=income) because income patterns run before merchant rules and the purchase description shares the payout prefix after strip_junk. $207.28 of Apparel spend vanishes from every spend total (BLS reconciliation, Q2 budget, Q3 shares) while simultaneously subtracting from monthly income in Q1's savings rate — a double distortion.

## clean.py

### line 152 — CONFIRMED
Dedupe assert demands the merged result equal a single pull's row count, which only holds for the current byte-identical fixture — the pipeline cannot ingest any future pull

Failure scenario: Next real collection (e.g. raw/chase_2026-08-15.csv with new August rows, the multi-pull workflow the collectors document) makes the deduped union legitimately larger than max(before.values()); clean.py hard-crashes with 'cross-file dedupe failed' even though dedupe worked. The fixture-specific check belongs in a test; the general invariant is per-key multiplicity == max within-pull multiplicity.

## anomalies.py

### line 14 — CONFIRMED
BASELINE_START/END and SCORE_START/END are hardcoded 2025-07..2026-07 literals, freezing 'this month' at July 2026 instead of deriving it from the data

Failure scenario: Run the pipeline after the next export (August 2026): anomalies.py silently rescores stale July against a stale baseline — new transactions are never scored and no error is raised. Deriving the score month from max(date) (as analyze.py already computes full_months) keeps the same code correct on every future pull.

## normalize.py

### line 214 — PLAUSIBLE
transaction_overrides match on (date, abs(amount)) alone — no account, sign, or description constraint, and no check that each override hits exactly one row

Failure scenario: Any coincidental row on the listed date with the same absolute amount (a Discover purchase of exactly $81.00 on 2026-07-28, or even a refund of that magnitude since abs() is used) is silently force-tagged Housing, skipping its merchant rule entirely. $81/$325/$800 are collision-prone round amounts; today each override happens to hit exactly 1 row, but nothing asserts or reports the match count.

### line 167 — PLAUSIBLE
Peer direction 'sign_dir = outgoing if raw_amount < 0' hardcodes Chase's sign convention, but peer description_patterns (^VENMO, ^APPLE CASH, ^WISE) also match Discover rows where purchases are raw-POSITIVE

Failure scenario: First Venmo/Apple Cash/Wise charge on the Discover card resolves as peer_direction='incoming' (inverted): categorize.py counts it as 'netting spend down' and zelle_review.csv shows the wrong direction; a Discover P2P refund reads as 'outgoing'. Zero Discover peer rows exist today, so the inversion is latent and will surface silently.

## categorize.py

### line 18 — PLAUSIBLE
BENCH_COL = 2 selects the BLS 'Less than $15,000' bracket by positional index; load_benchmark asserts row labels but never verifies the column header

Failure scenario: A refreshed bls_*.xlsx with one inserted/reordered income-bracket column (the loader globs for the newest file) makes every benchmark number in categorize.py AND analyze.py (Q3/Q4) silently become a different household's spending — plausible-looking output, no error. One assert that the header cell at BENCH_COL says 'Less than $15,000' (or locating the column by that string) closes it.

### line 91 — PLAUSIBLE
merchant can be written as empty string by normalize.py, read back from CSV as NaN (float), then sliced with r['merchant'][:40] -> TypeError

Failure scenario: A description like 'VENMO *VISA DIRECT NY' (counterparty regex-subs to '') or one consisting entirely of junk tokens produces merchant=''; pd.read_csv returns NaN for the empty field, and if such a row lands in the Uncategorized top-20 (line 91) or a flagged anomaly (anomalies.py line 71 merchant[:34]) the report crashes with 'float' object is not subscriptable. No such row exists in today's data, so the crash is latent; empty merchant also degrades clean.py's dedupe key.

## analyze.py

### line 33 — CONFIRMED
full_months excludes only the global min/max month, so 2024-08 (zero Discover rows) and 2024-09 (Discover starts 2024-09-17) are labeled 'full' months of two-account coverage

Failure scenario: Confirmed with current data (Chase from 2024-07-29, Discover from 2024-09-17): the coverage section reports 'Full calendar months: 2024-08 to 2026-06' though two of them are missing all or part of one account. Today's Q1/Q7 windows stop short of those months, but any longer window or shorter dataset silently absorbs the understated months into savings-rate and volatility numbers.

### line 56 — PLAUSIBLE
Q1's prior-window slice full_months[-12:-6] crashes or silently shrinks with fewer than 12 full months, and the aggregate rate divides by income with no zero guard (unlike the per-month loop)

Failure scenario: With <=6 full months, [-12:-6] is [] and months[0] raises IndexError; with 7-11 it silently compares a shorter 'prior 6 months' window. A window with zero Income rows raises ZeroDivisionError on 100*(inc-sp)/inc; one with negative net income (see the Grailed mis-tag) prints a sign-flipped rate. Current 23 full months mask all of it; any rerun on a shorter export triggers it.

### line 75 — PLAUSIBLE
Q2 divides each category total by `over` (actual minus budget), which can be zero or negative

Failure scenario: If trailing-90-day spend exactly equals the pro-rated budget, 100*amt/over raises ZeroDivisionError; if spend is under budget, every category prints an inverted-sign '% of overage' (nonsense output). Nothing guards over <= 0 before the loop — only today's $11k overage makes it work.
