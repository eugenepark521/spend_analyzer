import type { Metrics } from "@/lib/metrics";
import { monthLabel } from "@/lib/format";

// Dumbbell per category: gray dot = prior 6 months, green dot = latest 6.
export default function VolatilityPanel({ q7 }: { q7: Metrics["q7_volatility"] }) {
  const maxCv = Math.max(
    ...q7.categories.flatMap((c) => [c.cv, c.prior_cv ?? 0]),
  );
  const x = (v: number) => `${(100 * v) / maxCv}%`;
  // Summarise what the numbers actually did rather than asserting a trend that
  // only held for one dataset.
  const comparable = q7.categories.filter((c) => c.prior_cv !== null);
  const calmer = comparable.filter((c) => c.cv < (c.prior_cv as number)).length;
  const trend =
    comparable.length === 0
      ? "No category has a prior-window figure to compare against."
      : calmer === comparable.length
        ? "Every comparable category is swinging less than before."
        : calmer === 0
          ? "Every comparable category is swinging more than before."
          : `${calmer} of ${comparable.length} comparable categories are swinging less than before.`;

  return (
    <section className="panel" aria-labelledby="q7-h">
      <div className="panel-head">
        <div>
          <span className="kicker">Month-to-month swing (std ÷ mean)</span>
          <h2 id="q7-h">Which categories swing most</h2>
        </div>
        <div className="legend">
          <span className="key"><span className="swatch graphite" />prior 6 mo</span>
          <span className="key"><span className="swatch pine" />latest 6 mo</span>
        </div>
      </div>
      <div className="vol-list">
        {q7.categories.map((c) => (
          <div key={c.category} className="vol-row">
            <span className="cat">{c.category}</span>
            <span
              className="vol-track"
              role="img"
              aria-label={`${c.category}: coefficient of variation ${c.cv}${c.prior_cv !== null ? `, was ${c.prior_cv} in the prior six months` : ", no prior figure"}.`}
            >
              {c.prior_cv !== null && (
                <>
                  <span
                    className="link"
                    style={{
                      left: x(Math.min(c.cv, c.prior_cv)),
                      width: `calc(${x(Math.abs(c.cv - c.prior_cv))})`,
                    }}
                  />
                  <span className="dot prior" style={{ left: x(c.prior_cv) }} />
                </>
              )}
              <span className="dot now" style={{ left: x(c.cv) }} />
            </span>
            <span className="vol-vals">
              {c.prior_cv !== null ? `${c.prior_cv.toFixed(2)} → ${c.cv.toFixed(2)}` : `n/a → ${c.cv.toFixed(2)}`}
            </span>
          </div>
        ))}
      </div>
      <p className="caption">
        {monthLabel(q7.window.recent.start)}–{monthLabel(q7.window.recent.end)} vs.{" "}
        {monthLabel(q7.window.prior.start)}–{monthLabel(q7.window.prior.end)}, full
        two-account months only; categories averaging ≥ ${q7.min_monthly_avg}/month.{" "}
        {trend}
      </p>
    </section>
  );
}
