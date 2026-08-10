"""
categorize.py — stage 4 (task 13). Reads clean/transactions_clean.csv, assigns
each row a category from the BLS 14 (+ Transfer / Income / Uncategorized admin
buckets), writes clean/transactions_categorized.csv and clean/zelle_review.csv,
and prints the reconciliation against the BLS benchmark table in raw/.

Run: .venv/bin/python categorize.py
"""

import re
from pathlib import Path

import pandas as pd

from normalize import Resolver

CLEAN = Path("clean")
RAW = Path("raw")
BENCH_LABEL = "Less than $15,000"  # income bracket of the BLS cross-tab cell


def load_benchmark(resolver: Resolver) -> tuple[dict, float, str]:
    """Extract the 14 major-category means (and total expenditures) for the
    under-25 x lowest-income cell from the newest BLS pull in raw/.
    Returns (bench, total, provenance note) — callers print the note where
    it belongs in their own output."""
    path = sorted(RAW.glob("bls_*.xlsx"))[-1]
    table = pd.read_excel(path, header=None)
    items = table[0].astype(str).str.strip()
    # Locate the income-bracket column by its header label (the header row is
    # the one labelled 'Item'), never by position — a refreshed pull with an
    # inserted/reordered column must fail loudly, not return another bracket.
    hdr_rows = table.index[items == "Item"]
    assert len(hdr_rows) == 1, f"benchmark: expected 1 'Item' header row, got {len(hdr_rows)}"
    hdr = table.loc[hdr_rows[0]].astype(str).map(
        lambda s: re.sub(r"\s+", " ", s).strip())
    bench_cols = hdr.index[hdr == BENCH_LABEL]
    assert len(bench_cols) == 1, \
        f"benchmark: expected exactly 1 {BENCH_LABEL!r} column, got {len(bench_cols)}"
    bench_col = bench_cols[0]
    bench = {}
    for cat in resolver.bls:
        hits = table.loc[items == cat, bench_col]
        assert len(hits) == 1, f"benchmark: expected exactly 1 row for {cat!r}, got {len(hits)}"
        bench[cat] = float(hits.iloc[0])
    total = float(table.loc[items == "Average annual expenditures", bench_col].iloc[0])
    note = (f"Benchmark: {path.name}, column {BENCH_LABEL!r} "
            f"(avg annual expenditures ${total:,.0f})")
    return bench, total, note


def main():
    resolver = Resolver()
    df = pd.read_csv(CLEAN / "transactions_clean.csv")

    res = [
        resolver.resolve(d, acct, t, a, dt)
        for d, acct, t, a, dt in zip(df["description_raw"], df["account"],
                                     df["source_type"], df["amount_raw"],
                                     df["date"])
    ]
    resolver.assert_overrides_hit_once()
    df["category"] = [r.category for r in res]
    df["matched_rule"] = [r.matched_rule for r in res]
    df["is_peer"] = [r.is_peer for r in res]
    df["peer_direction"] = [r.peer_direction for r in res]
    df["counterparty"] = [r.counterparty for r in res]
    # spend = the 14 BLS categories plus Uncategorized (real outflows we just
    # can't attribute yet); Transfer and Income are excluded by construction
    df["in_spend"] = df["category"].isin(resolver.bls + ["Uncategorized"])

    used = set(df["category"].unique())
    unknown = used - set(resolver.bls) - set(resolver.admin)
    assert not unknown, f"rows assigned categories outside the taxonomy: {unknown}"

    df.to_csv(CLEAN / "transactions_categorized.csv", index=False)
    print(f"Wrote {CLEAN / 'transactions_categorized.csv'} ({len(df)} rows)\n")

    # --- peer-payment review file ---
    peers = df[df["is_peer"]].copy()
    peers["abs_amount"] = peers["amount"].abs()
    peers = peers.sort_values("abs_amount", ascending=False)
    review_cols = ["date", "counterparty", "amount", "peer_direction",
                   "category", "account", "description_raw"]
    peers[review_cols].to_csv(CLEAN / "zelle_review.csv", index=False)

    misc_default = peers[peers["category"] == "Miscellaneous"]
    ambiguous = peers[peers["peer_direction"] == "ambiguous"]
    print("=== Peer payments (Zelle/QuickPay/Venmo/Apple Cash/Wise) ===")
    print(f"{len(peers)} rows written to clean/zelle_review.csv")
    out = peers[peers["peer_direction"] == "outgoing"]
    inc = peers[peers["peer_direction"] == "incoming"]
    print(f"  outgoing: {len(out)} rows, ${out['amount'].sum():,.2f} gross spend")
    print(f"  incoming: {len(inc)} rows, ${-inc['amount'].sum():,.2f} netting spend down")
    print(f"  ambiguous direction (left Uncategorized): {len(ambiguous)}")
    print(f"Riding on the Miscellaneous default: {len(misc_default)} rows, "
          f"net ${misc_default['amount'].sum():,.2f} "
          f"(gross outgoing ${misc_default.loc[misc_default['amount'] > 0, 'amount'].sum():,.2f})")

    # --- uncategorized report ---
    unc = df[df["category"] == "Uncategorized"].copy()
    print(f"\n=== Uncategorized ===\n{len(unc)} rows, net ${unc['amount'].sum():,.2f}")
    top = unc.reindex(unc["amount"].abs().sort_values(ascending=False).index).head(20)
    print("Top 20 by amount (add rules for these in categories.yaml):")
    for _, r in top.iterrows():
        print(f"  {r['date']}  {r['amount']:9.2f}  {r['merchant'][:40]:40}  {r['description_raw'][:60]}")

    # --- reconciliation against the benchmark ---
    bench, bench_total, bench_note = load_benchmark(resolver)
    print(bench_note)
    days = (pd.to_datetime(df["date"].max()) - pd.to_datetime(df["date"].min())).days + 1
    spend = df[df["in_spend"]]
    my_total = spend["amount"].sum()
    my_annual_total = my_total * 365.25 / days

    print(f"\n=== Reconciliation: my spend vs BLS (under 25, <$15k income) ===")
    print(f"My data: {df['date'].min()} to {df['date'].max()} ({days} days); "
          f"totals annualised by x365.25/{days}")
    hdr = f"{'category':38} {'my total':>10} {'my annual':>10} {'my %':>6} {'BLS annual':>10} {'BLS %':>6}"
    print(hdr + "\n" + "-" * len(hdr))
    for cat in resolver.bls + ["Uncategorized"]:
        mine = spend.loc[spend["category"] == cat, "amount"].sum()
        annual = mine * 365.25 / days
        b = bench.get(cat)
        bs = f"{b:10,.0f} {100 * b / bench_total:5.1f}%" if b is not None else f"{'—':>10} {'—':>6}"
        print(f"{cat:38} {mine:10,.2f} {annual:10,.0f} {100 * mine / my_total:5.1f}% {bs}")
    print("-" * len(hdr))
    print(f"{'TOTAL (spend)':38} {my_total:10,.2f} {my_annual_total:10,.0f} {'100.0%':>6} "
          f"{bench_total:10,.0f} {'100.0%':>6}")

    # category-structure checks the task requires
    spend_cats = set(spend["category"]) - {"Uncategorized"}
    assert spend_cats <= set(bench), \
        f"categories in my spend missing from benchmark: {spend_cats - set(bench)}"
    missing = [c for c in resolver.bls if c not in bench]
    assert not missing, f"benchmark table is missing BLS categories: {missing}"
    zero = [c for c in resolver.bls if spend.loc[spend['category'] == c, 'amount'].sum() == 0]
    print(f"\nAll spend categories exist in the benchmark; all 14 benchmark "
          f"categories present in the table above.")
    if zero:
        print(f"Benchmark categories where I have $0 recorded: {', '.join(zero)}")

    excl = df[~df["in_spend"]]
    print("\n=== Excluded from spend (kept for reconciliation) ===")
    for cat in ["Transfer", "Income"]:
        sub = excl[excl["category"] == cat]
        print(f"  {cat}: {len(sub)} rows, net ${sub['amount'].sum():,.2f}")


if __name__ == "__main__":
    main()
