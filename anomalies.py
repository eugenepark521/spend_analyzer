"""
anomalies.py — task 15 modelling stage. Flags transactions in the scored
month that fall outside the account's own history, using modified z-scores
(Iglewicz-Hoaglin) on log1p-transformed amounts: per-category baselines with
a pooled global fallback for thin categories. Method, rejected alternatives,
and failure modes are written up in analysis.md's modelling section.

compute_anomalies() returns the scored frames and windows as one dict so
export_dashboard_data.py (task 18) writes the dashboard's metrics.json from
the same logic that prints this report.

Run: .venv/bin/python anomalies.py
"""

import numpy as np
import pandas as pd

MIN_N = 30          # baseline transactions needed for per-category statistics
FLAG_AT = 3.5       # |modified z| threshold (Iglewicz & Hoaglin's convention)
CONSISTENCY = 0.6745  # makes MAD comparable to SD under normality


def _med_mad(arr: np.ndarray) -> tuple[float, float]:
    med = float(np.median(arr))
    return med, float(np.median(np.abs(arr - med)))


def make_scorer(base: pd.DataFrame, percat: list[str]):
    """score(row) -> (modified z, model name): per-category baseline where
    supported, global pool otherwise; a degenerate (MAD=0) category is
    rescored globally. Median/MAD are precomputed once per baseline."""
    stats = {"global": _med_mad(base["logamt"].to_numpy())}
    for c in percat:
        stats[c] = _med_mad(base.loc[base["category"] == c, "logamt"].to_numpy())

    def score(row) -> tuple[float, str]:
        m = row["category"] if row["category"] in percat else "global"
        med, mad = stats[m]
        if mad == 0:
            m = "global"
            med, mad = stats["global"]
        z = CONSISTENCY * (row["logamt"] - med) / mad if mad else float("nan")
        return z, m

    return score


def compute_anomalies(df: pd.DataFrame) -> dict:
    """Windows, baselines, and scored frames for the current data, no printing."""
    # Scoring population: real spend outflows only. Refunds/credits (negative
    # amounts) are excluded — the log transform needs positives, and "unusual
    # refund" is a different question than "unusual purchase".
    sp = df[df["in_spend"] & (df["amount"] > 0)].copy()
    sp["logamt"] = np.log1p(sp["amount"])

    # "This month" (Q5) = calendar month of the newest transaction in the data;
    # baseline = the trailing 12 full months before it.
    score_month = pd.to_datetime(df["date"]).max().to_period("M")
    score_start, score_end = (score_month.start_time.strftime("%Y-%m-%d"),
                              score_month.end_time.strftime("%Y-%m-%d"))
    base_start, base_end = ((score_month - 12).start_time.strftime("%Y-%m-%d"),
                            (score_month - 1).end_time.strftime("%Y-%m-%d"))

    base = sp[sp["date"].between(base_start, base_end)]
    target = sp[sp["date"].between(score_start, score_end)].copy()
    assert len(base) and len(target), (
        f"empty baseline ({len(base)}) or score month ({len(target)}) — "
        f"windows {base_start}..{base_end} / {score_start}..{score_end}")

    # Per-category baselines where supported; Uncategorized is a mixed bag by
    # construction, so it always scores against the global pool.
    counts = base.groupby("category").size()
    percat = [c for c in counts.index
              if counts[c] >= MIN_N and c != "Uncategorized"]

    score = make_scorer(base, percat)
    zs, ms = zip(*(score(r) for _, r in target.iterrows()))
    target["score"], target["model"] = zs, ms

    # Threshold sanity check: self-score the baseline year with the same
    # rules. If nothing ever crosses FLAG_AT, the threshold is vacuous.
    retro = base.copy()
    zs, ms = zip(*(score(r) for _, r in retro.iterrows()))
    retro["score"], retro["model"] = zs, ms

    return {
        "base_start": base_start, "base_end": base_end,
        "score_start": score_start, "score_end": score_end,
        "base": base, "target": target, "retro": retro,
        "counts": {c: int(n) for c, n in counts.items()}, "percat": percat,
        "flagged": target[target["score"].abs() >= FLAG_AT],
        "retro_flagged": retro[retro["score"].abs() >= FLAG_AT],
    }


def _print_rows(rows: pd.DataFrame):
    for _, r in rows.sort_values("score", key=abs, ascending=False).iterrows():
        print(f"  {r['date']}  {r['amount']:9,.2f}  {r['score']:+5.2f}  "
              f"{r['category']:22.22} vs {r['model']:22.22} {r['merchant'][:34]}")


def main():
    df = pd.read_csv("clean/transactions_categorized.csv")
    A = compute_anomalies(df)
    base, target = A["base"], A["target"]

    print(f"Baseline {A['base_start']}..{A['base_end']}: {len(base)} spend rows; "
          f"scoring {A['score_start'][:7]}: {len(target)} rows")
    print(f"Per-category models (n>={MIN_N}): "
          f"{', '.join(f'{c} (n={A['counts'][c]})' for c in sorted(A['percat']))}")
    print(f"Global fallback pool: n={len(base)} for all other categories\n")

    print(f"=== Flagged at |score| >= {FLAG_AT}: {len(A['flagged'])} of {len(target)} ===")
    _print_rows(A["flagged"])

    print(f"\n=== Top 10 by |score| (context, incl. unflagged) ===")
    _print_rows(target.sort_values("score", key=abs, ascending=False).head(10))

    print(f"\n=== Retrospective: baseline year self-scored, {len(A['retro_flagged'])} of "
          f"{len(A['retro'])} rows cross |{FLAG_AT}| ===")
    _print_rows(A["retro_flagged"])


if __name__ == "__main__":
    main()
