// The dashboard's only data source. metrics.json is the pipeline's contract
// (see ../decisions.md): export_dashboard_data.py writes it, this file reads
// it. No number is computed or hardcoded on the UI side.
import { readFile } from "node:fs/promises";
import path from "node:path";

export interface Tx {
  date: string;
  merchant: string;
  amount: number;
  category: string;
  model: string;
  score: number;
}

export interface Metrics {
  meta: {
    generated_at: string;
    date_range: { start: string; end: string };
    rows: number;
    accounts: string[];
    coverage: { month: string; rows: Record<string, number>; full: boolean }[];
    full_months: { start: string; end: string; count: number };
    coverage_note: string;
  };
  q1_savings: {
    current: Window;
    prior: Window;
    monthly: { month: string; income: number; spend: number; rate: number | null }[];
  };
  q2_budget: {
    window: { start: string; end: string; days: number };
    budget_monthly: number;
    budget_prorated: number;
    actual: number;
    overage: number;
    categories: { category: string; amount: number; pct_of_overage: number | null }[];
  };
  q3_benchmark: {
    source: string;
    my_total: number;
    bench_total: number;
    categories: {
      category: string;
      my_amount: number;
      my_share: number;
      bls_amount: number;
      bls_share: number;
      diff_pp: number;
    }[];
    uncategorized: { amount: number; share: number };
  };
  q4_fixed: {
    fixed_categories: string[];
    mine: Split;
    benchmark: Split;
  };
  q5_anomalies: {
    month: string;
    scored: number;
    threshold: number;
    flagged: Tx[];
    near_misses: Tx[];
    baseline: { start: string; end: string; n: number };
    models: { category: string; n: number }[];
    min_n: number;
    retro: { n: number; flagged: Tx[] };
  };
  q6_forecast: { available: boolean; reason: string; details: string };
  q7_volatility: {
    window: { recent: Span; prior: Span };
    min_monthly_avg: number;
    categories: { category: string; cv: number; prior_cv: number | null }[];
  };
}

interface Window {
  start: string;
  end: string;
  income: number;
  spend: number;
  rate: number | null;
}
interface Split { fixed: number; total: number; fixed_share: number }
interface Span { start: string; end: string }

// Swappable data path (task 19 points this at a synthetic sample file):
// METRICS_PATH, absolute or relative to the dashboard directory.
export async function loadMetrics(): Promise<Metrics> {
  const p = path.resolve(process.cwd(), process.env.METRICS_PATH ?? "data/metrics.json");
  return JSON.parse(await readFile(p, "utf8")) as Metrics;
}
