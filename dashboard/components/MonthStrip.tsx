"use client";

import { useMemo, useState } from "react";
import type { Metrics } from "@/lib/metrics";
import { money, monthLabel, signedPct } from "@/lib/format";

type Monthly = Metrics["q1_savings"]["monthly"][number];

// The signature element: every coverage month as an income/spend bar pair;
// partial-coverage months render as hollow slots so the caveat is visible,
// not footnoted. Hover/focus a month for its numbers (readout below — the
// values are also in the sr-only table, so the pointer is never required).
export default function MonthStrip({
  monthly,
  coverage,
  note,
}: {
  monthly: Monthly[];
  coverage: Metrics["meta"]["coverage"];
  note: string;
}) {
  const byMonth = useMemo(
    () => new Map(monthly.map((r) => [r.month, r])),
    [monthly],
  );
  const max = useMemo(
    () => Math.max(...monthly.flatMap((r) => [r.income, r.spend])),
    [monthly],
  );
  const last = monthly[monthly.length - 1];
  const [active, setActive] = useState<Monthly>(last);

  const h = (v: number) => `${Math.max((100 * v) / max, 1.5)}%`;

  return (
    <div className="panel strip">
      <div className="panel-head">
        <div>
          <span className="kicker">Month by month</span>
          <h2>Income vs. spending, every covered month</h2>
        </div>
        <div className="legend" aria-hidden="true">
          <span className="key"><span className="swatch graphite" />income</span>
          <span className="key"><span className="swatch pine" />spending</span>
          <span className="key"><span className="swatch hollow" />partial coverage, excluded</span>
        </div>
      </div>

      <div className="strip-bars" role="img" aria-label="Monthly income and spending bars; details in the table below.">
        {coverage.map((c) => {
          const r = byMonth.get(c.month);
          if (!c.full || !r) {
            return (
              <span key={c.month} className="strip-month partial" title={`${monthLabel(c.month)}: partial account coverage, excluded`}>
                <span className="hollow-slot" />
              </span>
            );
          }
          const isActive = active.month === r.month;
          return (
            <button
              key={c.month}
              type="button"
              className={`strip-month${isActive ? " active" : ""}`}
              onMouseEnter={() => setActive(r)}
              onFocus={() => setActive(r)}
              aria-label={`${monthLabel(r.month)}: income ${money(r.income)}, spending ${money(r.spend)}`}
            >
              <span className="bar income" style={{ height: h(r.income) }} />
              <span className="bar spend" style={{ height: h(r.spend) }} />
            </button>
          );
        })}
      </div>

      <p className="strip-readout" aria-live="polite">
        <strong>{monthLabel(active.month)}</strong> — income {money(active.income)},
        spending {money(active.spend)}
        {active.rate !== null && <> · savings rate {signedPct(active.rate)}</>}
      </p>
      <p className="footnote-mono">{note}</p>

      {/* div wrapper, not class-on-table: a table ignores width:1px (floors
          at min-content) and would silently widen the page on mobile */}
      <div className="sr-only">
      <table>
        <caption>Monthly income and spending, full-coverage months</caption>
        <thead>
          <tr><th scope="col">Month</th><th scope="col">Income</th><th scope="col">Spending</th><th scope="col">Savings rate</th></tr>
        </thead>
        <tbody>
          {monthly.map((r) => (
            <tr key={r.month}>
              <th scope="row">{r.month}</th>
              <td>{money(r.income)}</td>
              <td>{money(r.spend)}</td>
              <td>{r.rate !== null ? signedPct(r.rate) : "n/a"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
