# BRIEF.md

## Intent

A personal spending analyzer. Takes raw bank exports, cleans and categorises them onto the BLS Consumer Expenditure Survey taxonomy, and compares spending shares against comparable households. Built to answer a fixed set of questions (`questions.md`), not to be a general-purpose finance tool.

## Decisions

- **BLS CEX as the benchmark.** A comparison only means something against a defined cohort, so categories match BLS's 14 exactly — a rule assigning any other name fails at load.
- **Rules in YAML, not code.** Merchant normalisation and categorisation are an ordered rule list, editable without touching Python.
- **Anomaly detection over forecasting.** About two years of monthly observations, structurally lumpy top categories, and a mid-series change in spending pattern make a category-level forecast unfittable. Transaction-level anomaly scoring has far more observations to work with.
- **Flat JSON over SQLite.** The dashboard's metric set is fixed and small, so a query engine buys nothing. Python computes every number; the frontend only renders.
- **Synthetic data is the default.** The tracked dataset and the deployed site are synthetic. Real data requires an explicit env var and writes only to gitignored paths, so a misconfigured deploy cannot serve real finances.

## Constraints

- No bank API — exports are downloaded manually, and the BLS site blocks bots. Collection is a documented manual step, not automation.
- Real transaction data never enters the repo. Personal matching rules live in a gitignored overlay (`categories.local.yaml`); without it the pipeline runs but miscategorises, so the refresh command checks for it first.
- The dashboard answers every question on one screen.

## Open questions

- Whether below-benchmark total spend reflects genuinely lower spending or incomplete capture — cash never passes through either account.
- The anomaly detector's precision is untested. Every flag so far has been a legitimate lumpy payment, because the dataset contains no known errors to catch.
- The benchmark's income filter is a proxy, not a match, for a household funded substantially by non-earnings inflows.
