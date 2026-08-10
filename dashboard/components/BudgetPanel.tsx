import type { Metrics } from "@/lib/metrics";
import { dateLabel, money, pct } from "@/lib/format";

export default function BudgetPanel({ q2 }: { q2: Metrics["q2_budget"] }) {
  const over = q2.overage > 0;
  const top3 = q2.categories.slice(0, 3);
  // Presentation only: where the budget tick sits along the actual-spend bar.
  const tickPct = Math.min((100 * q2.budget_prorated) / Math.max(q2.actual, q2.budget_prorated), 100);

  return (
    <section className="panel" aria-labelledby="q2-h">
      <div className="panel-head">
        <div>
          <span className="kicker">Last {q2.window.days} days</span>
          <h2 id="q2-h">Against a {money(q2.budget_monthly)}/month budget</h2>
        </div>
        <span className="big">
          {money(q2.actual)}{" "}
          {over && <span className="neg">({money(q2.overage)} over)</span>}
        </span>
      </div>

      <div
        className="meter"
        role="img"
        aria-label={`Spent ${money(q2.actual)} against a budget of ${money(q2.budget_prorated)} for the window.`}
      >
        <span className="budget-tick" style={{ left: `${tickPct}%` }} />
      </div>
      <div className="meter-scale">
        <span>$0</span>
        <span style={{ position: "absolute", left: `${tickPct}%`, transform: "translateX(-50%)" }}>
          budget {money(q2.budget_prorated)}
        </span>
        <span>{money(q2.actual)}</span>
      </div>

      <div className="chips">
        {top3.map((c) => (
          <span key={c.category} className="chip">
            <strong>{c.category}</strong> {money(c.amount)}
            {c.pct_of_overage !== null && <> · {pct(c.pct_of_overage, 0)} of overage</>}
          </span>
        ))}
      </div>

      <p className="caption">
        {dateLabel(q2.window.start)}–{dateLabel(q2.window.end)}. The budget is a
        single monthly total, not per-category targets — shares are of the
        overage, not of a category budget.
      </p>
    </section>
  );
}
