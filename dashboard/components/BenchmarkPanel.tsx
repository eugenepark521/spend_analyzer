"use client";

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Metrics } from "@/lib/metrics";
import { money, pct, signedPp } from "@/lib/format";

const PINE = "#006b41";
const GRAPHITE = "#898781";
const INK = "#16211c";
const MUTED = "#6b6963";
const HAIRLINE = "#e3e1d8";
const CHART_TOP = 4;    // BarChart margin.top
const CHART_XAXIS = 30; // recharts default x-axis band height

// Display names only — data stays keyed by the pipeline's category strings.
const SHORT: Record<string, string> = {
  "Apparel and services": "Apparel & services",
  "Personal insurance and pensions": "Insurance & pensions",
  "Tobacco products and smoking supplies": "Tobacco & smoking",
  "Personal care products and services": "Personal care",
  "Alcoholic beverages": "Alcohol",
};

export default function BenchmarkPanel({ q3 }: { q3: Metrics["q3_benchmark"] }) {
  const rows = [...q3.categories]
    .sort((a, b) => b.diff_pp - a.diff_pp)
    .map((r) => ({ ...r, name: SHORT[r.category] ?? r.category }));

  return (
    <section className="panel" aria-labelledby="q3-h">
      <div className="panel-head">
        <div>
          <span className="kicker">Share of total spending</span>
          <h2 id="q3-h">Spending vs. comparable households</h2>
        </div>
        <div className="legend">
          <span className="key"><span className="swatch pine" />me</span>
          <span className="key"><span className="swatch graphite" />comparable households</span>
        </div>
      </div>

      {/* CHART_TOP/CHART_XAXIS must match the BarChart margins below; the
          absolutely-positioned ±pp column relies on recharts spacing its 14
          category bands evenly across the plot height. */}
      <div style={{ position: "relative" }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            top: CHART_TOP,
            bottom: CHART_XAXIS,
            right: 0,
            width: 44,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {rows.map((r) => (
            <span
              key={r.category}
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                fontFamily: "var(--font-data)",
                fontSize: 10.5,
                color: INK,
              }}
            >
              {Math.abs(r.diff_pp) >= 2 ? signedPp(r.diff_pp) : ""}
            </span>
          ))}
        </div>
      <ResponsiveContainer width="100%" height={396}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: CHART_TOP, right: 50, bottom: 0, left: 0 }}
          barGap={2}
          barCategoryGap={6}
        >
          <XAxis
            type="number"
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fontSize: 10, fill: MUTED, fontFamily: "var(--font-data)" }}
            axisLine={{ stroke: HAIRLINE }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={128}
            tick={{ fontSize: 11, fill: MUTED }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(0,0,0,0.03)" }}
            isAnimationActive={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as (typeof rows)[number];
              return (
                <div style={{ background: "#fcfcfb", border: `1px solid ${HAIRLINE}`, borderRadius: 8, padding: "8px 10px", fontSize: 11.5, color: INK }}>
                  <strong>{r.category}</strong>
                  <div>Me: {pct(r.my_share)} ({money(r.my_amount)})</div>
                  <div>Comparable: {pct(r.bls_share)} ({money(r.bls_amount)}/yr)</div>
                  <div>Difference: {signedPp(r.diff_pp)}</div>
                </div>
              );
            }}
          />
          <Bar dataKey="my_share" name="Me" fill={PINE} barSize={8} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          <Bar dataKey="bls_share" name="Comparable households" fill={GRAPHITE} barSize={8} radius={[0, 4, 4, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      </div>

      <p className="caption">
        Above the benchmark where the green bar leads. Uncategorized outflows
        ({pct(q3.uncategorized.share)} of my spending, {money(q3.uncategorized.amount)})
        have no benchmark line and are excluded here.
      </p>
      <p className="footnote-mono">
        BLS Consumer Expenditure Survey, under-25 households with income under
        $15,000 · {q3.source}
      </p>

      {/* div wrapper, not class-on-table — see MonthStrip */}
      <div className="sr-only">
      <table>
        <caption>My spending share vs. BLS benchmark share by category</caption>
        <thead>
          <tr><th scope="col">Category</th><th scope="col">My share</th><th scope="col">Benchmark share</th><th scope="col">Difference (pp)</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.category}>
              <th scope="row">{r.category}</th>
              <td>{pct(r.my_share)}</td>
              <td>{pct(r.bls_share)}</td>
              <td>{signedPp(r.diff_pp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </section>
  );
}
