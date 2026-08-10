import type { Metrics } from "@/lib/metrics";
import { money, monthLabel } from "@/lib/format";

// Q5's real result is zero flags — shown as a stated result with the closest
// calls beneath it, so the panel reads as a working detector, not a bug.
export default function AnomaliesPanel({ q5 }: { q5: Metrics["q5_anomalies"] }) {
  const hasFlags = q5.flagged.length > 0;
  const list = hasFlags ? q5.flagged : q5.near_misses;

  return (
    <section className="panel" aria-labelledby="q5-h">
      <span className="kicker">{monthLabel(q5.month)} anomaly scan</span>
      <h2 id="q5-h">Transactions outside my own pattern</h2>
      <p className="big">
        {hasFlags ? <span className="neg">{q5.flagged.length}</span> : q5.flagged.length}{" "}
        <span style={{ fontSize: 13, fontWeight: 400 }}>of {q5.scored} flagged</span>
      </p>
      <div className="near-list">
        <span className="kicker">{hasFlags ? "flagged" : "closest calls"}</span>
        {list.map((t) => (
          <div key={`${t.date}-${t.merchant}-${t.amount}`} className={`near-row${hasFlags ? " flag-row" : ""}`}>
            <span className="score">{t.score > 0 ? "+" : ""}{t.score.toFixed(2)}</span>
            <span className="who" title={`${t.merchant} · ${t.category}`}>{t.merchant}</span>
            <span className="amt">{money(t.amount, 2)}</span>
          </div>
        ))}
      </div>
      <p className="caption">
        Flag at score ≥ {q5.threshold} vs. my own {q5.baseline.n}-transaction
        year. Same rules on last year: {q5.retro.flagged.length} of {q5.retro.n}{" "}
        flagged — all legitimate one-offs (tuition, rent).
      </p>
    </section>
  );
}
