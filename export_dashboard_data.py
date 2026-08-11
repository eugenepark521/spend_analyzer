"""
export_dashboard_data.py — stage 7 (task 18). Calls the same compute functions
behind analyze.py (Q1-Q4, Q7) and anomalies.py (Q5) and writes every number
the dashboard needs to dashboard/data/metrics.json — one key per question in
questions.md plus a meta block. The dashboard only renders this file:
metrics.json is the contract between pipeline and UI (see decisions.md), and
no analysis logic exists outside Python.

Run: .venv/bin/python export_dashboard_data.py   (after categorize.py)
"""

import json
import sys
from datetime import datetime, timezone

import pandas as pd

from analyze import compute_metrics
from anomalies import FLAG_AT, MIN_N, compute_anomalies
from config import CLEAN_DIR, DATASET, METRICS_OUT
from normalize import Resolver

OUT = METRICS_OUT
NEAR_MISSES = 5  # top |score| rows shown when nothing is flagged


def d(x: float) -> float:
    """Dollars: round for a stable, diff-able JSON file."""
    return round(float(x), 2)


def tx_records(rows: pd.DataFrame) -> list[dict]:
    return [{"date": r["date"], "merchant": r["merchant"],
             "amount": d(r["amount"]), "category": r["category"],
             "model": r["model"], "score": round(float(r["score"]), 2)}
            for _, r in rows.iterrows()]


def check_output_matches_dataset():
    """The sample file is the ONE thing dashboard/.gitignore force-tracks and
    the deploy serves, so writing anything else there would publish it. The
    output path and the dataset stamp must therefore agree in both directions:
    real data can never land in the sample file, and sample data can never
    masquerade as the personal export."""
    is_sample_path = OUT.name == "sample.metrics.json"
    if is_sample_path and DATASET != "sample":
        sys.exit(f"Refusing to write {OUT}: that file is tracked and deployed, "
                 f"but SPEND_DATASET is {DATASET!r}. Set SPEND_DATASET=sample "
                 f"(or use build_sample.py).")
    if DATASET == "sample" and not is_sample_path:
        sys.exit(f"Refusing to write {OUT}: SPEND_DATASET=sample must be "
                 f"written to a file named sample.metrics.json.")


def main():
    check_output_matches_dataset()
    resolver = Resolver()
    df = pd.read_csv(CLEAN_DIR / "transactions_categorized.csv")
    M = compute_metrics(df, resolver)
    A = compute_anomalies(df)

    cov = M["cov"]
    fm = M["full_months"]
    cur, prior = M["q1"]["windows"]
    q2, q3, q4, q7 = M["q2"], M["q3"], M["q4"], M["q7"]
    target = A["target"]
    near = target.sort_values("score", key=abs, ascending=False).head(NEAR_MISSES)

    metrics = {
        "meta": {
            # "sample" => synthetic demo data; the dashboard labels the page
            # from this field alone, so the label can never be forgotten.
            "dataset": DATASET,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "date_range": {"start": M["date_min"], "end": M["date_max"]},
            "rows": M["rows"],
            "accounts": sorted(cov.columns),
            "coverage": [{"month": m,
                          "rows": {a: int(cov.loc[m, a]) for a in cov.columns},
                          "full": m in fm}
                         for m in cov.index],
            "full_months": {"start": fm[0], "end": fm[-1], "count": len(fm)},
            "account_spans": M["account_spans"],
            # Derived per account — never hardcoded, so the note stays true of
            # whatever dataset was actually processed.
            "coverage_note": (
                f"Months outside {fm[0]}..{fm[-1]} have partial account "
                f"coverage ("
                + ", ".join(f"{a} starts {s['start']}"
                            for a, s in sorted(M["account_spans"].items()))
                + f"; the export ends {M['date_max']}) and are excluded from "
                f"all monthly series."),
        },
        "q1_savings": {
            "current": {"start": cur["months"][0], "end": cur["months"][-1],
                        "income": d(cur["income"]), "spend": d(cur["spend"]),
                        "rate": round(cur["rate"], 1) if cur["rate"] is not None else None},
            "prior": {"start": prior["months"][0], "end": prior["months"][-1],
                      "income": d(prior["income"]), "spend": d(prior["spend"]),
                      "rate": round(prior["rate"], 1) if prior["rate"] is not None else None},
            "monthly": [{"month": r["month"], "income": d(r["income"]),
                         "spend": d(r["spend"]),
                         "rate": round(r["rate"], 1) if r["rate"] is not None else None}
                        for r in M["q1"]["monthly_full"]],
        },
        "q2_budget": {
            "window": {"start": q2["start"], "end": q2["end"], "days": 90},
            "budget_monthly": 1000.0,
            "budget_prorated": d(q2["budget"]),
            "actual": d(q2["total"]),
            "overage": d(q2["over"]),
            "categories": [{"category": c, "amount": d(a),
                            "pct_of_overage": round(100 * a / q2["over"], 1)
                            if q2["over"] > 0 else None}
                           for c, a in q2["bycat"]],
        },
        "q3_benchmark": {
            "source": q3["note"],
            "my_total": d(q3["my_total"]),
            "bench_total": d(q3["bench_total"]),
            "categories": [{"category": r["category"],
                            "my_amount": d(r["mine"]),
                            "my_share": round(r["my_share"], 1),
                            "bls_amount": d(r["bench"]),
                            "bls_share": round(r["bls_share"], 1),
                            "diff_pp": round(r["diff_pp"], 1)}
                           for r in q3["rows"]],
            "uncategorized": {"amount": d(q3["uncategorized"]),
                              "share": round(100 * q3["uncategorized"] / q3["my_total"], 1)},
        },
        "q4_fixed": {
            "fixed_categories": q4["fixed_categories"],
            "mine": {"fixed": d(q4["my_fixed"]), "total": d(q4["my_total"]),
                     "fixed_share": round(100 * q4["my_fixed"] / q4["my_total"], 1)},
            "benchmark": {"fixed": d(q4["bls_fixed"]), "total": d(q4["bench_total"]),
                          "fixed_share": round(100 * q4["bls_fixed"] / q4["bench_total"], 1)},
        },
        "q5_anomalies": {
            "month": A["score_start"][:7],
            "scored": int(len(target)),
            "threshold": FLAG_AT,
            "flagged": tx_records(A["flagged"]),
            "near_misses": tx_records(near),
            "baseline": {"start": A["base_start"], "end": A["base_end"],
                         "n": int(len(A["base"]))},
            "models": [{"category": c, "n": A["counts"][c]}
                       for c in sorted(A["percat"])],
            "min_n": MIN_N,
            "retro": {"n": int(len(A["retro"])),
                      "flagged": tx_records(A["retro_flagged"])},
        },
        "q6_forecast": {
            "available": False,
            # Dataset-independent on purpose: the reasoning is structural, and
            # this string is published, so it must not describe the author's
            # own circumstances.
            "reason": ("No forecast is produced, deliberately: the modelling "
                       "stage chose anomaly detection over forecasting — about "
                       "two years of monthly observations, structurally lumpy "
                       "top categories (tuition, rent), and a mid-series change "
                       "in spending pattern make a category-level monthly "
                       "forecast unfittable and unvalidatable."),
            "details": "analysis.md — 'Why this over forecasting'",
        },
        "q7_volatility": {
            "window": {"recent": {"start": q7["recent"][0], "end": q7["recent"][-1]},
                       "prior": {"start": q7["prior"][0], "end": q7["prior"][-1]}},
            "min_monthly_avg": 50,
            "categories": [{"category": c, "cv": round(v, 2),
                            "prior_cv": (round(q7["cv_prior"][c], 2)
                                         if c in q7["cv_prior"] else None)}
                           for c, v in q7["cv_recent"].items()],
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(metrics, indent=1) + "\n")
    n_keys = len(metrics) - 1
    print(f"Wrote {OUT}: {n_keys} question keys + meta, "
          f"{M['rows']} source rows {M['date_min']}..{M['date_max']}")


if __name__ == "__main__":
    main()
