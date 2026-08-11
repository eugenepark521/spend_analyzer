"""
analyze.py — stage 6 (task 14). Reads clean/transactions_categorized.csv and
prints the numbers behind every answer in analysis.md: data coverage by month,
monthly savings rate, 90-day budget drift, BLS benchmark comparison (reusing
categorize.py's benchmark loader), fixed-vs-discretionary split, and
category volatility. Q5 (anomalies) and Q6 (forecast) need the modelling
method chosen in task 15 and are not computed here.

compute_metrics() returns every number as one dict so export_dashboard_data.py
(task 18) writes the dashboard's metrics.json from the same logic that prints
this report — nothing is recomputed anywhere else.

Run: .venv/bin/python analyze.py
"""

import pandas as pd

from categorize import load_benchmark
from config import CLEAN_DIR
from normalize import Resolver

# Fixed vs discretionary judgement call (documented in analysis.md): fixed =
# committed obligations, everything else (incl. Uncategorized) discretionary.
FIXED = ["Housing", "Healthcare", "Personal insurance and pensions", "Education"]


def compute_metrics(df: pd.DataFrame, resolver: Resolver) -> dict:
    """Every number behind analysis.md, computed once, no printing."""
    df = df.copy()
    df["month"] = df["date"].str[:7]
    spend = df[df["in_spend"]]

    # --- data coverage ---
    cov = df.pivot_table(index="month", columns="account", values="date",
                         aggfunc="count", fill_value=0)
    # A month is "full" only if it lies strictly inside EVERY account's own
    # coverage window: each account's first/last months are partial (export
    # window; Discover history starts 2024-09-17, later than Chase's).
    amin, amax = df.groupby("account")["month"].min(), df.groupby("account")["month"].max()
    full_months = sorted(m for m in cov.index
                         if all(amin[a] < m < amax[a] for a in cov.columns))

    monthly_spend = spend.groupby("month")["amount"].sum()
    income = df[df["category"] == "Income"]
    monthly_income = -income.groupby("month")["amount"].sum()

    # --- Q1: savings rate, trailing 6 full months ---
    assert len(full_months) >= 12, (
        f"Q1 needs >=12 full months (trailing 6 + prior 6), have "
        f"{len(full_months)} — window slices below would be wrong")
    last6, prior6 = full_months[-6:], full_months[-12:-6]
    monthly_full = []
    for m in full_months:
        inc = float(monthly_income.get(m, 0.0))
        sp = float(monthly_spend.get(m, 0.0))
        monthly_full.append({"month": m, "income": inc, "spend": sp,
                             "rate": 100 * (inc - sp) / inc if inc else None})
    q1_months = monthly_full[-6:]
    q1_windows = []
    for label, months in [("6-month aggregate", last6), ("prior 6 months  ", prior6)]:
        inc = float(sum(monthly_income.get(m, 0) for m in months))
        sp = float(sum(monthly_spend.get(m, 0) for m in months))
        # a zero/negative income window makes the rate a divide-by-zero or a
        # sign-flipped nonsense number — return None and let callers say so
        q1_windows.append({"label": label, "months": list(months), "income": inc,
                           "spend": sp,
                           "rate": 100 * (inc - sp) / inc if inc > 0 else None})

    # --- Q2: 90-day spend vs $1,000/month budget ---
    end = pd.to_datetime(df["date"].max())
    start = end - pd.Timedelta(days=89)
    w = spend[pd.to_datetime(spend["date"]).between(start, end)]
    budget = 1000 * 12 / 365.25 * 90
    total = float(w["amount"].sum())
    q2_bycat = [(c, float(a)) for c, a in
                w.groupby("category")["amount"].sum()
                .sort_values(ascending=False).items()]

    # --- Q3: category share vs BLS benchmark (reuses task-13 loader) ---
    bench, bench_total, bench_note = load_benchmark(resolver)
    my_total = float(spend["amount"].sum())
    q3_rows = []
    for cat in resolver.bls:
        mine = float(spend.loc[spend["category"] == cat, "amount"].sum())
        mp, bp = 100 * mine / my_total, 100 * bench[cat] / bench_total
        q3_rows.append({"category": cat, "mine": mine, "bench": float(bench[cat]),
                        "my_share": mp, "bls_share": bp, "diff_pp": mp - bp})
    unc = float(spend.loc[spend["category"] == "Uncategorized", "amount"].sum())

    # --- Q4: fixed vs discretionary ---
    my_fixed = float(spend.loc[spend["category"].isin(FIXED), "amount"].sum())
    bls_fixed = float(sum(bench[c] for c in FIXED))

    # --- Q7: category volatility (CV of monthly totals), 6-month windows ---
    cat_month = (spend[spend["month"].isin(full_months)]
                 .pivot_table(index="month", columns="category", values="amount",
                              aggfunc="sum", fill_value=0.0))

    def cv(window_months):
        sub = cat_month.loc[cat_month.index.isin(window_months)]
        mean, std = sub.mean(), sub.std()
        keep = mean[mean >= 50].index  # skip near-zero categories: CV meaningless
        return (std[keep] / mean[keep]).sort_values(ascending=False)

    cv_recent, cv_prior = cv(last6), cv(prior6)

    account_spans = {a: {"start": g["date"].min(), "end": g["date"].max()}
                     for a, g in df.groupby("account")}
    return {
        "date_min": df["date"].min(), "date_max": df["date"].max(),
        "rows": len(df), "cov": cov, "full_months": full_months,
        "account_spans": account_spans,
        "q1": {"months": q1_months, "windows": q1_windows,
               "monthly_full": monthly_full},
        "q2": {"start": str(start.date()), "end": str(end.date()),
               "budget": float(budget), "total": total, "over": float(total - budget),
               "bycat": q2_bycat},
        "q3": {"note": bench_note, "rows": q3_rows, "my_total": my_total,
               "bench_total": float(bench_total), "uncategorized": unc},
        "q4": {"fixed_categories": list(FIXED), "my_fixed": my_fixed,
               "my_total": my_total, "bls_fixed": bls_fixed,
               "bench_total": float(bench_total)},
        "q7": {"recent": list(last6), "prior": list(prior6),
               "cv_recent": {c: float(v) for c, v in cv_recent.items()},
               "cv_prior": {c: float(v) for c, v in cv_prior.items()}},
    }


def main():
    resolver = Resolver()
    df = pd.read_csv(CLEAN_DIR / "transactions_categorized.csv")
    M = compute_metrics(df, resolver)

    print("=== Coverage: row counts by month x account ===")
    print(M["cov"].to_string())
    fm = M["full_months"]
    print(f"\nDate range: {M['date_min']} to {M['date_max']}")
    print(f"Full calendar months: {fm[0]} to {fm[-1]} "
          f"({len(fm)} months)")

    print("\n=== Q1: savings rate by month, trailing 6 full months ===")
    for r in M["q1"]["months"]:
        if r["rate"] is not None:
            print(f"  {r['month']}  income {r['income']:9,.2f}  spend {r['spend']:9,.2f}  "
                  f"savings rate {r['rate']:7.1f}%")
        else:
            print(f"  {r['month']}  income {r['income']:9,.2f}  spend {r['spend']:9,.2f}  "
                  f"savings rate    n/a (no income)")
    for wdw in M["q1"]["windows"]:
        rate = f"{wdw['rate']:.1f}%" if wdw["rate"] is not None else "n/a (income <= 0)"
        print(f"  {wdw['label']} ({wdw['months'][0]}..{wdw['months'][-1]}): "
              f"income {wdw['income']:,.2f}, spend {wdw['spend']:,.2f}, rate {rate}")

    print("\n=== Q2: trailing 90 days vs $1,000/month budget ===")
    q2 = M["q2"]
    print(f"  window {q2['start']} to {q2['end']}; budget ${q2['budget']:,.2f} "
          f"(90 days at $1,000/mo); actual ${q2['total']:,.2f}; overage ${q2['over']:,.2f}")
    if q2["over"] > 0:
        print("  category totals in window (top contributors to overage):")
        for cat, amt in q2["bycat"]:
            print(f"    {cat:38} {amt:9,.2f}  = {100 * amt / q2['over']:5.1f}% of overage")
    else:
        # at/under budget: '% of overage' is a div-by-zero or sign-inverted
        print("  at/under budget — category totals in window:")
        for cat, amt in q2["bycat"]:
            print(f"    {cat:38} {amt:9,.2f}")

    print("\n=== Q3: my category share vs BLS share (percentage points) ===")
    q3 = M["q3"]
    print(q3["note"])
    for r in sorted(q3["rows"], key=lambda r: -r["diff_pp"]):
        print(f"  {r['category']:38} me {r['my_share']:5.1f}%  "
              f"BLS {r['bls_share']:5.1f}%  {r['diff_pp']:+5.1f}pp")
    print(f"  (Uncategorized holds {100 * q3['uncategorized'] / q3['my_total']:.1f}% "
          f"of my spend, no BLS counterpart)")

    print("\n=== Q4: fixed vs discretionary ===")
    q4 = M["q4"]
    print(f"  fixed = {', '.join(q4['fixed_categories'])}")
    print(f"  me:  fixed {100 * q4['my_fixed'] / q4['my_total']:.1f}% / "
          f"discretionary {100 * (1 - q4['my_fixed'] / q4['my_total']):.1f}% "
          f"(${q4['my_fixed']:,.2f} of ${q4['my_total']:,.2f})")
    print(f"  BLS: fixed {100 * q4['bls_fixed'] / q4['bench_total']:.1f}% / "
          f"discretionary {100 * (1 - q4['bls_fixed'] / q4['bench_total']):.1f}% "
          f"(${q4['bls_fixed']:,.0f} of ${q4['bench_total']:,.0f})")

    print("\n=== Q7: month-over-month volatility (std/mean of monthly totals) ===")
    q7 = M["q7"]
    print(f"  trailing 6 full months ({q7['recent'][0]}..{q7['recent'][-1]}), "
          f"categories averaging >=$50/mo:")
    for cat, v in q7["cv_recent"].items():
        prev = q7["cv_prior"].get(cat)
        trend = f"prior 6mo {prev:4.2f}" if prev is not None else "prior 6mo  n/a"
        print(f"    {cat:38} CV {v:4.2f}   ({trend})")


if __name__ == "__main__":
    main()
