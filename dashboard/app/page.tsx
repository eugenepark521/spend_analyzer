import { isSample, loadMetrics } from "@/lib/metrics";
import { dateLabel } from "@/lib/format";
import HeroSavings from "@/components/HeroSavings";
import MonthStrip from "@/components/MonthStrip";
import BenchmarkPanel from "@/components/BenchmarkPanel";
import BudgetPanel from "@/components/BudgetPanel";
import FixedPanel from "@/components/FixedPanel";
import AnomaliesPanel from "@/components/AnomaliesPanel";
import VolatilityPanel from "@/components/VolatilityPanel";
import ForecastPanel from "@/components/ForecastPanel";

// Re-read metrics.json on every request so a pipeline rerun shows on refresh.
export const dynamic = "force-dynamic";

export default async function Page() {
  const { metrics: m, sourceFile } = await loadMetrics();
  const { meta } = m;
  const sample = isSample(m);

  return (
    <main className="shell">
      <header className="masthead">
        <div className="title-row">
          <h1>Two years of spending, audited</h1>
          {/* Driven by meta.dataset, so it disappears by itself when the
              pipeline is pointed at real data — it cannot be forgotten. */}
          {sample && (
            <span className="sample-flag">
              Sample data — synthetic, not real finances
            </span>
          )}
        </div>
        <p className="meta">
          {meta.rows.toLocaleString("en-US")} transactions · {meta.accounts.join(" + ")} ·{" "}
          {dateLabel(meta.date_range.start)} → {dateLabel(meta.date_range.end)} · generated{" "}
          {meta.generated_at.slice(0, 10)} · source: {sourceFile}
        </p>
      </header>

      <section className="hero" aria-label="Savings rate and monthly history">
        <HeroSavings q1={m.q1_savings} />
        <MonthStrip
          monthly={m.q1_savings.monthly}
          coverage={meta.coverage}
          note={meta.coverage_note}
        />
      </section>

      <section className="grid">
        <BenchmarkPanel q3={m.q3_benchmark} />
        <div className="col">
          <BudgetPanel q2={m.q2_budget} />
          <FixedPanel q4={m.q4_fixed} />
        </div>
        <div className="col">
          <AnomaliesPanel q5={m.q5_anomalies} />
          <VolatilityPanel q7={m.q7_volatility} />
        </div>
      </section>

      <ForecastPanel q6={m.q6_forecast} />
    </main>
  );
}
