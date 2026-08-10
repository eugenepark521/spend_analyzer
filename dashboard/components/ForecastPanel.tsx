import type { Metrics } from "@/lib/metrics";

// Honest negative result: no forecast exists, on purpose. This panel states
// the choice; it never shows a number, trendline, or placeholder that could
// be mistaken for one.
export default function ForecastPanel({ q6 }: { q6: Metrics["q6_forecast"] }) {
  if (q6.available) return null; // contract allows a future model to add one
  return (
    <section className="panel forecast" aria-labelledby="q6-h">
      <div>
        <span className="kicker">Next month’s forecast</span>
        <h2 id="q6-h" className="none">None — deliberately.</h2>
      </div>
      <p>
        {q6.reason} <span className="footnote-mono">({q6.details})</span>
      </p>
    </section>
  );
}
