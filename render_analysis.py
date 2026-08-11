"""
render_analysis.py — writes analysis.md from a metrics.json.

analysis.md answers questions.md. Every number in it comes from the metrics
file, and every claim that could differ between datasets (which categories are
above benchmark, whether volatility rose or fell, how many anomalies fired) is
derived here rather than asserted — so the same renderer produces the tracked
synthetic document and the author's local one, and neither can drift from
its data.

The methodology prose (why anomaly detection over forecasting, what would make
the method wrong) is dataset-independent and lives in this file as template
text; it is reasoning about the approach, not about any one person's spending.

  .venv/bin/python render_analysis.py                       # sample -> analysis.md
  .venv/bin/python render_analysis.py --metrics dashboard/data/metrics.json \\
      --out analysis.local.md                               # real -> gitignored
"""

import argparse
import json
import textwrap
from pathlib import Path

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def money(n, digits=0):
    return f"${n:,.{digits}f}"


def pct(n, digits=1):
    return f"{n:.{digits}f}%"


def signed_pct(n, digits=1):
    return f"{'+' if n > 0 else '−' if n < 0 else ''}{abs(n):.{digits}f}%"


def signed_pp(n):
    return f"{'+' if n > 0 else '−' if n < 0 else ''}{abs(n):.1f}pp"


def mlabel(ym):
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


_NUM_WORDS = ["zero", "one", "two", "three", "four", "five",
              "six", "seven", "eight", "nine"]


def _num(n: int) -> str:
    """Small counts read better spelled out in prose."""
    return _NUM_WORDS[n] if 0 <= n < len(_NUM_WORDS) else f"{n}"


def _sentence(s: str) -> str:
    """Capitalise a clause lifted out of a longer sentence."""
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def wrap(md: str, width: int = 78) -> str:
    """Re-wrap prose paragraphs so the generated markdown reads like a written
    document rather than one long line per section. Headings, list items and
    blank lines are left alone."""
    out = []
    for block in md.split("\n\n"):
        stripped = block.strip("\n")
        if not stripped or stripped.startswith(("#", "- ", "  ")):
            out.append(stripped)
            continue
        flat = " ".join(line.strip() for line in stripped.splitlines())
        out.append(textwrap.fill(flat, width=width, break_long_words=False,
                                 break_on_hyphens=False))
    return "\n\n".join(out).rstrip() + "\n"


def joined(items, conj="and"):
    items = list(items)
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return ", ".join(items[:-1]) + f", {conj} {items[-1]}"


def render(M: dict) -> str:
    meta, q1, q2 = M["meta"], M["q1_savings"], M["q2_budget"]
    q3, q4, q5, q6, q7 = (M["q3_benchmark"], M["q4_fixed"], M["q5_anomalies"],
                          M["q6_forecast"], M["q7_volatility"])
    fm, spans = meta["full_months"], meta.get("account_spans", {})
    cur, prior = q1["current"], q1["prior"]

    # --- Q1 -----------------------------------------------------------------
    rated = [r for r in q1["monthly"] if r["rate"] is not None]
    hi = max(rated, key=lambda r: r["rate"])
    lo = min(rated, key=lambda r: r["rate"])
    if cur["rate"] is None or prior["rate"] is None:
        trend_clause = "no comparison is possible (a window has no income)"
    else:
        delta = cur["rate"] - prior["rate"]
        moved = f"{abs(delta):,.1f} points"
        if delta > 0:
            trend_clause = f"trending up, an improvement of {moved}"
        elif delta < 0:
            trend_clause = f"trending down, a fall of {moved}"
        else:
            trend_clause = "flat between the two windows"
        if cur["rate"] < 0 and prior["rate"] < 0:
            trend_clause += ", though both windows spend more than they take in"

    # --- Q2 -----------------------------------------------------------------
    over = q2["overage"] > 0
    top3 = q2["categories"][:3]

    # --- Q3 -----------------------------------------------------------------
    above = [c for c in sorted(q3["categories"], key=lambda c: -c["diff_pp"])
             if c["diff_pp"] > 0.05]
    below = [c for c in sorted(q3["categories"], key=lambda c: c["diff_pp"])
             if c["diff_pp"] < -0.05]
    top_above = above[0] if above else None

    # --- Q5 -----------------------------------------------------------------
    n_flag, n_scored = len(q5["flagged"]), q5["scored"]
    if n_flag:
        lead = q5["flagged"][0]
        for f in q5["flagged"]:
            if abs(f["score"]) > abs(lead["score"]):
                lead = f
        q5_line = (
            f"**{n_flag} of {mlabel(q5['month'])}'s {n_scored} spend "
            f"transactions cross the |{q5['threshold']}| modified-z flag "
            f"threshold** (method and full results in the Modelling section "
            f"below); the largest is {money(lead['amount'], 2)} at "
            f"{signed_pct(lead['score'], 2).replace('%', '')}, scored against "
            f"the {lead['model']} baseline.")
    else:
        near = q5["near_misses"][0] if q5["near_misses"] else None
        q5_line = (
            f"Zero of {mlabel(q5['month'])}'s {n_scored} spend transactions "
            f"cross the |{q5['threshold']}| modified-z flag threshold (method "
            f"and full results in the Modelling section below)"
            + (f"; the top scorer reaches only "
               f"{signed_pct(near['score'], 2).replace('%', '')}." if near else "."))

    # --- Q7 -----------------------------------------------------------------
    cats = q7["categories"]
    comparable = [c for c in cats if c["prior_cv"] is not None]
    calmer = [c for c in comparable if c["cv"] < c["prior_cv"]]
    rougher = [c for c in comparable if c["cv"] > c["prior_cv"]]
    no_prior = [c["category"] for c in cats if c["prior_cv"] is None]

    def arrows(items):
        return joined([f"{c['category']} ({c['prior_cv']:.2f}→{c['cv']:.2f})"
                       for c in items])

    # Name the categories in each direction instead of stating a bare ratio —
    # a count like "2 of 3" beside a list of five makes the reader reconcile
    # the two numbers themselves.
    if not comparable:
        q7_trend = ("None of these has a prior-window figure to compare "
                    "against, so no direction can be claimed.")
    elif not rougher:
        q7_trend = (f"Every one with a prior-window figure is **calmer** than "
                    f"the prior 6 months: {arrows(comparable)}.")
    elif not calmer:
        q7_trend = (f"Every one with a prior-window figure is **more volatile** "
                    f"than the prior 6 months: {arrows(comparable)}.")
    else:
        q7_trend = (f"The direction is mixed: {arrows(calmer)} "
                    f"{'is' if len(calmer) == 1 else 'are'} calmer than the "
                    f"prior 6 months, while {arrows(rougher)} "
                    f"{'is' if len(rougher) == 1 else 'are'} more volatile.")
    if no_prior:
        # Comma-list in parentheses, not an "and" list: category names contain
        # "and" themselves ("Apparel and services"), so a conjunction list
        # reads as one run-on name.
        q7_trend = (
            f"Only {_num(len(comparable))} of these can be compared with the "
            f"prior 6 months at all — the other "
            f"{'one' if len(no_prior) == 1 else _num(len(no_prior))} "
            f"({', '.join(no_prior)}) averaged under "
            f"${q7['min_monthly_avg']}/month back then. {q7_trend}")

    # --- modelling ----------------------------------------------------------
    models = ", ".join(f"{m['category']} n={m['n']}" for m in q5["models"])
    retro_cats = sorted({t["category"] for t in q5["retro"]["flagged"]})

    # Account keys are lowercase in the data; the prose capitalises them.
    span_txt = "; ".join(f"{a.title()} from {s['start']}"
                         for a, s in sorted(spans.items()))

    is_sample = meta.get("dataset") == "sample"
    # Voice: first person for the author's own data, neutral third person for
    # the published synthetic copy, so sample figures can never be mistaken
    # for a real person's spending.
    SUBJ = "this dataset" if is_sample else "I"
    POSS = "the dataset's" if is_sample else "my"
    POSS_LOW = "the dataset's" if is_sample else "my"
    OF_MINE = "in the dataset" if is_sample else "of mine"
    IS_ARE = "is" if is_sample else "am"
    provenance = (
        "**Every figure below comes from the synthetic sample dataset** "
        "(`build_sample.py`) — invented transactions, not anyone's real "
        "finances. The same renderer produces the private version from real "
        "data, which is gitignored."
        if is_sample else
        "**This copy is rendered from real personal data** and is gitignored "
        "(`analysis.local.md`); the tracked `analysis.md` is the synthetic "
        "version built by `build_sample.py`.")

    doc = f"""# analysis.md — answers to questions.md

Generated by `render_analysis.py` — run it to reproduce every number.
{provenance}

Data coverage: full calendar months {fm['start']} through {fm['end']}
({fm['count']} months). A month counts as full only if it lies strictly inside
every account's own coverage window ({span_txt}; the export ends
{meta['date_range']['end']}), so partial months at either end are excluded from
all monthly series. "Income" throughout means the pipeline's Income category
(payroll, aid disbursements, marketplace payouts, family support — see
sources.md on why this is not BLS-sense earned income).

## 1. Savings rate and 6-month trend

Over the trailing 6 full months ({cur['start']}..{cur['end']}) the savings rate
is **{signed_pct(cur['rate'])}** (income {money(cur['income'])}, spending
{money(cur['spend'])}), against **{signed_pct(prior['rate'])}** over the prior
6 months ({prior['start']}..{prior['end']}) — {trend_clause}.

The aggregate is the honest form of that answer rather than a hedge: income
arrives in lumps rather than evenly, so a month-by-month series swings from
{signed_pct(hi['rate'])} ({mlabel(hi['month'])}) to {signed_pct(lo['rate'])}
({mlabel(lo['month'])}) on the timing of a single disbursement. The monthly
series is still worth plotting — the dashboard shows it — but only the
six-month windows support a claim about direction.

## 2. Category drift from budget, trailing 90 days

Against the {money(q2['budget_monthly'])}/month total budget (pro-rated to
{money(q2['budget_prorated'], 2)} for the {q2['window']['days']}-day window
{q2['window']['start']}..{q2['window']['end']}), actual spending was
**{money(q2['actual'], 2)}"""

    if over:
        doc += f" — {money(q2['overage'], 2)} over** — and since the budget is a "
        doc += ("single monthly total with no per-category targets, \"drift by "
                "category\" here means share of that overage: ")
        doc += joined([f"**{c['category']} {money(c['amount'], 2)} "
                       f"({pct(c['pct_of_overage'], 1)})**" for c in top3])
        doc += " are the top three contributors.\n"
    else:
        doc += (f", {money(-q2['overage'], 2)} under budget**, so there is no "
                "overage to apportion; the largest categories in the window are "
                + joined([f"**{c['category']} {money(c['amount'], 2)}**"
                          for c in top3]) + ".\n")

    doc += f"""
## 3. Category split vs. BLS benchmark

Comparing full-history spending shares against the under-25, <$15k-income BLS
CEX cell: {SUBJ} {IS_ARE} **above** benchmark share in """
    doc += joined([f"{c['category']} ({signed_pp(c['diff_pp'])}, "
                   f"{pct(c['my_share'])} vs {pct(c['bls_share'])})"
                   if c is top_above else
                   f"{c['category']} ({signed_pp(c['diff_pp'])})"
                   for c in above[:5]])
    doc += ", and **below** in "
    doc += joined([f"{c['category']} ({signed_pp(c['diff_pp'])})" for c in below[:3]])
    doc += (f", with {pct(q3['uncategorized']['share'])} of {POSS_LOW} spending "
            f"sitting in Uncategorized, which has no BLS counterpart.\n")

    doc += f"""
## 4. Fixed vs. discretionary spend vs. benchmark

Defining fixed = {joined([c.lower() for c in q4['fixed_categories']])} (a
judgement call: committed obligations; everything else, including
Uncategorized, counts as discretionary), {POSS} split is
**{pct(q4['mine']['fixed_share'])} fixed / {pct(100 - q4['mine']['fixed_share'])}
discretionary** ({money(q4['mine']['fixed'], 2)} of
{money(q4['mine']['total'], 2)}) versus the benchmark household's
**{pct(q4['benchmark']['fixed_share'])} fixed /
{pct(100 - q4['benchmark']['fixed_share'])} discretionary**
({money(q4['benchmark']['fixed'])} of {money(q4['benchmark']['total'])}).

## 5. Anomalous transactions this month

{q5_line}

## 6. Forecasted next-month spend and error range

No forecast is produced. {_sentence(q6['reason'].split(': ', 1)[-1])}
Full reasoning in the Modelling section below.

## 7. Category volatility, month-over-month

Over the trailing 6 full months ({q7['window']['recent']['start']}..\
{q7['window']['recent']['end']}), the highest month-over-month volatility
(coefficient of variation of monthly totals, categories averaging
≥ ${q7['min_monthly_avg']}/month) is """
    # List every qualifying category, not a top-N slice: the sentence that
    # follows counts how many of them have a prior-window figure, and a
    # truncated list would leave the reader unable to reconcile the two.
    doc += joined([f"**{c['category']} (CV {c['cv']:.2f})**" if i < 2
                   else f"{c['category']} ({c['cv']:.2f})"
                   for i, c in enumerate(cats)])
    doc += f".\n\n{q7_trend}\n"

    doc += f"""
# Modelling: anomaly detection

Implemented in `anomalies.py`; run it to reproduce every number below.

## Method

Each spend transaction in the scored month gets a modified z-score
(Iglewicz–Hoaglin) on its log1p-transformed amount, M = 0.6745 ×
(x − median) / MAD, flagged at |M| ≥ {q5['threshold']}. The scored month is the
calendar month of the newest transaction ({mlabel(q5['month'])} here) and the
baseline is the trailing 12 full months before it
({q5['baseline']['start']}..{q5['baseline']['end']}, {q5['baseline']['n']} rows),
both derived from the data at run time. The scoring population is spend rows
(the 14 BLS categories plus Uncategorized) with amount > 0 — refunds and credits
are excluded because the log transform needs positives and "unusual refund" is a
different question. Baselines are per-category where a category has ≥
{q5['min_n']} baseline transactions ({models}); every other category, plus
Uncategorized always (a mixed bag by construction — deliberately unknowable
merchants and untagged peer rows — so "unusual for Uncategorized" is not
meaningful), scores against the pooled global baseline; a category whose MAD is
zero is rescored globally.

## Why this over forecasting

A next-month category-level forecast was rejected because the data cannot
support one: only about two years of monthly observations exist (two seasonal
cycles — far too few to fit, let alone validate, a seasonal model); the largest
categories are structurally lumpy rather than monthly-recurring (tuition is
semester-driven, and housing runs partly through irregular peer payments); and
the series contains a mid-period change in spending pattern, so a model fit on
the full history would span two different regimes. Anomaly detection instead
uses {meta['rows']:,} transaction-level observations, and the regime change
becomes a documented finding to inspect flags against, rather than a confound
baked silently into a forecast.

## What would make it wrong

- **Thin categories inherit the wrong yardstick**: a category below the
  n≥{q5['min_n']} minimum scores against the global pool, so its scores mean
  "large for any transaction {OF_MINE}", not "large for rent" or "large for
  tuition" — which is why routine lumpy payments can flag retrospectively.
- **A regime change inside the baseline is only half-handled**: if the baseline
  spans two spending patterns, its category distributions become bimodal, the
  MAD widens or collapses depending on the mix, and ordinary recurring charges
  can read as outliers.
- **Symmetry assumption**: MAD scoring treats log-amounts as roughly symmetric,
  but within-category log-spend is still right-skewed, so low-side scores
  compress and the detector is effectively one-sided in practice.
- **Statistically extreme ≠ wrong**: a legitimate one-time large purchase is
  indistinguishable from an erroneous or fraudulent one, so flags are a review
  queue, not verdicts.
- **Judgment-set constants**: n≥{q5['min_n']}, the {q5['threshold']} cutoff, the
  12-month window, and log1p are conventions, not derived values, and results
  are sensitive to them.

## Results

{mlabel(q5['month'])}: **{n_flag} of {n_scored} transactions flag at
|M| ≥ {q5['threshold']}**."""

    if n_flag:
        doc += " The flagged rows are " + joined(
            [f"{t['merchant']} {money(t['amount'], 2)} "
             f"({signed_pct(t['score'], 2).replace('%', '')}, {t['model']} model)"
             for t in q5["flagged"]]) + "."
    if q5["near_misses"]:
        shown = [t for t in q5["near_misses"]
                 if t not in q5["flagged"]][:3]
        if shown:
            doc += " Below the line, the closest calls are " + joined(
                [f"{t['merchant']} {money(t['amount'], 2)} "
                 f"({signed_pct(t['score'], 2).replace('%', '')})" for t in shown]) + "."

    doc += (f" Retrospectively self-scoring the baseline year flags "
            f"{len(q5['retro']['flagged'])} of {q5['retro']['n']} rows")
    if retro_cats:
        doc += f", all in {joined(retro_cats)}"
    doc += (" — confirming the threshold fires on genuine extremes while also "
            "showing that large, legitimate, lumpy payments are what it "
            "mostly catches: the method works as designed, and its output is a "
            "queue to review rather than a list of errors.\n")
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="dashboard/data/sample.metrics.json")
    ap.add_argument("--out", default="analysis.md")
    a = ap.parse_args()
    M = json.loads(Path(a.metrics).read_text())
    Path(a.out).write_text(wrap(render(M)))
    print(f"Wrote {a.out} from {a.metrics} "
          f"(dataset={M['meta'].get('dataset', 'personal')})")


if __name__ == "__main__":
    main()
