"""
clean.py — stage 3 (task 13). Reads ALL scrubbed pulls in raw/, normalises
merchants/signs/dates, dedupes across overlapping pulls, and writes
clean/transactions_clean.csv.

Dedupe contract (see decisions.md):
  key = (account, date, normalised merchant, normalised amount).
  If a key appears N times WITHIN one pull, N copies are legitimate distinct
  transactions and all N are kept. Across pulls of the same account, the final
  multiplicity of a key is the MAX multiplicity seen in any single pull
  (rows taken from the latest pull that attains it).

Run: .venv/bin/python clean.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

from normalize import Resolver

RAW = Path("raw")
OUT = Path("clean")
KEY = ["account", "date", "merchant", "amount"]

# FX descriptions embed the foreign amount and rate; the Amount column must be
# the USD conversion of them. Used to *assert* USD denomination, not to convert.
FX_DISCOVER = re.compile(r"(\d+(?:\.\d+)?)\s*@\s*0*(\.\d+)\s*JPY", re.I)
FX_CHASE = re.compile(r"Yen\s+(\d+)\s*X\s*([\d.]+)\s*\(EXCHG RTE\)", re.I)


def load_chase(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    assert list(df.columns) == ["Details", "Posting Date", "Description", "Amount", "Type"], \
        f"{path}: unexpected Chase columns {list(df.columns)}"
    amount = pd.to_numeric(df["Amount"], errors="raise")
    # Chase convention: debits negative. The Details flag mostly agrees but
    # merchant refunds keep Details=DEBIT with a positive amount, so the sign
    # column is authoritative. CREDIT rows must never be negative, though.
    assert ((df["Details"] != "CREDIT") | (amount > 0)).all(), \
        f"{path}: CREDIT row with negative amount"
    refunds = int(((df["Details"] == "DEBIT") & (amount > 0)).sum())
    if refunds:
        print(f"  note: {path.name}: {refunds} DEBIT-flagged rows with positive "
              f"amounts (merchant refunds) — sign taken as authoritative")
    out = pd.DataFrame({
        "account": "chase",
        "date": pd.to_datetime(df["Posting Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"),
        # Chase exports a single date and it is a posting date; kept in both
        # columns so post_date is never silently empty.
        "post_date": pd.to_datetime(df["Posting Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"),
        "description_raw": df["Description"],
        "source_type": df["Type"],
        "amount_raw": amount,
        "amount": -amount,  # normalise: expenses positive, income/credits negative
        "source_file": path.name,
    })
    return out


def load_discover(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    assert list(df.columns) == ["Trans. Date", "Post Date", "Description", "Amount", "Category"], \
        f"{path}: unexpected Discover columns {list(df.columns)}"
    amount = pd.to_numeric(df["Amount"], errors="raise")
    out = pd.DataFrame({
        "account": "discover",
        # transaction date is canonical; posting date kept alongside
        "date": pd.to_datetime(df["Trans. Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"),
        "post_date": pd.to_datetime(df["Post Date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"),
        "description_raw": df["Description"],
        "source_type": df["Category"],
        "amount_raw": amount,
        "amount": amount,  # Discover already has purchases positive
        "source_file": path.name,
    })
    return out


def assert_usd(df: pd.DataFrame) -> int:
    """Every amount must be numeric USD. For foreign-currency rows the
    description embeds `foreign_amount x rate`; assert it reproduces the USD
    Amount within a cent, proving Amount is already converted."""
    assert df["amount"].notna().all(), "non-numeric amounts found"
    checked = 0
    for _, row in df.iterrows():
        m = FX_DISCOVER.search(str(row["description_raw"])) or \
            FX_CHASE.search(str(row["description_raw"]))
        if m:
            implied = float(m.group(1)) * float(m.group(2))
            assert abs(implied - abs(row["amount_raw"])) <= 0.02, (
                f"FX row does not reconcile to USD: {row['description_raw']!r} "
                f"implied {implied:.2f} vs amount {row['amount_raw']}"
            )
            checked += 1
    return checked


def dedupe(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """frames: {pull_filename: df} for ONE account, oldest pull first.
    Keeps, per key, the max within-pull multiplicity, rows taken from the
    latest pull attaining that multiplicity."""
    counted = []
    for name, df in frames.items():
        df = df.copy()
        df["dup_rank"] = df.groupby(KEY).cumcount()  # 0..N-1 within this pull
        counted.append(df)
    allrows = pd.concat(counted, ignore_index=True)
    # For each (key, dup_rank) slot keep the row from the latest pull. A pull
    # with N copies fills slots 0..N-1, so the union of slots = max multiplicity.
    allrows = allrows.sort_values("source_file").drop_duplicates(
        subset=KEY + ["dup_rank"], keep="last")
    return allrows.drop(columns="dup_rank")


def main():
    OUT.mkdir(exist_ok=True)
    resolver = Resolver()

    pulls: dict[str, dict[str, pd.DataFrame]] = {"chase": {}, "discover": {}}
    for path in sorted(RAW.glob("chase_*.csv")):
        pulls["chase"][path.name] = load_chase(path)
    for path in sorted(RAW.glob("discover_*.csv")):
        pulls["discover"][path.name] = load_discover(path)
    if not pulls["chase"] or not pulls["discover"]:
        sys.exit("missing chase or discover pulls in raw/")

    # normalise merchants (same resolver the categorise stage uses)
    for account, frames in pulls.items():
        for name, df in frames.items():
            res = [
                resolver.resolve(d, account, t, a, dt)
                for d, t, a, dt in zip(df["description_raw"], df["source_type"],
                                       df["amount_raw"], df["date"])
            ]
            df["merchant"] = [r.merchant for r in res]

    print("=== Dedupe across pulls ===")
    deduped = {}
    for account, frames in pulls.items():
        before = {name: len(df) for name, df in frames.items()}
        deduped[account] = dedupe(frames)
        after = len(deduped[account])
        for name, n in before.items():
            print(f"  {name}: {n} rows")
        print(f"  -> {account} after dedupe: {after} rows")
        # Dedupe contract: per key, final multiplicity == max multiplicity seen
        # in any single pull. (Pulls may add new rows, so the union can exceed
        # any one pull's count.)
        expected = (pd.concat([df.groupby(KEY).size() for df in frames.values()],
                              axis=1).fillna(0).max(axis=1).astype(int))
        got = (deduped[account].groupby(KEY).size()
               .reindex(expected.index, fill_value=0))
        bad = expected[got != expected]
        assert bad.empty, (
            f"{account}: {len(bad)} keys violate per-key max-multiplicity "
            f"invariant — cross-file dedupe failed, e.g. {bad.index[0]}")
        print(f"  OK: all {len(expected)} keys at max within-pull multiplicity "
              f"({sum(before.values()) - after} overlap rows collapsed)")

    clean = pd.concat(deduped.values(), ignore_index=True)
    fx_checked = assert_usd(clean)
    print(f"\n=== Currency ===\nAll {len(clean)} amounts numeric USD; "
          f"{fx_checked} foreign-currency rows reconciled against embedded FX rate.")

    clean = clean.sort_values(["date", "account", "description_raw"]).reset_index(drop=True)
    cols = ["account", "date", "post_date", "description_raw", "merchant",
            "amount", "amount_raw", "source_type", "source_file"]
    clean[cols].to_csv(OUT / "transactions_clean.csv", index=False)
    print(f"\nWrote {OUT / 'transactions_clean.csv'} ({len(clean)} rows)")

    # --- merchant collapse report ---
    n_raw = clean["description_raw"].nunique()
    n_merch = clean["merchant"].nunique()
    print(f"\n=== Merchant normalisation ===\n"
          f"{n_raw} distinct raw descriptions -> {n_merch} distinct merchants")
    groups = (clean.groupby("merchant")["description_raw"].nunique()
              .sort_values(ascending=False).head(20))
    print("\nTop 20 collapse groups (merchant <- # distinct raw descriptions):")
    for merchant, n in groups.items():
        samples = clean.loc[clean["merchant"] == merchant, "description_raw"].unique()[:3]
        print(f"  {n:4d}  {merchant}")
        for s in samples:
            print(f"          e.g. {s[:90]}")


if __name__ == "__main__":
    main()
