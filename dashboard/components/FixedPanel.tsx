import type { Metrics } from "@/lib/metrics";
import { money, pct } from "@/lib/format";

function SplitBar({
  who,
  fixedShare,
  color,
  tint,
}: {
  who: string;
  fixedShare: number;
  color: string;
  tint: string;
}) {
  return (
    <div className="split-row">
      <div className="who">{who}</div>
      <div
        className="split-bar"
        role="img"
        aria-label={`${who}: ${pct(fixedShare)} committed, ${pct(100 - fixedShare, 1)} flexible.`}
      >
        <span className="seg" style={{ width: `${fixedShare}%`, background: color }} />
        <span className="seg" style={{ flex: 1, background: tint }} />
      </div>
      <div className="split-label">
        <span>committed {pct(fixedShare)}</span>
        <span>flexible {pct(100 - fixedShare, 1)}</span>
      </div>
    </div>
  );
}

export default function FixedPanel({ q4 }: { q4: Metrics["q4_fixed"] }) {
  return (
    <section className="panel" aria-labelledby="q4-h">
      <span className="kicker">Committed vs. flexible</span>
      <h2 id="q4-h">How much is locked in</h2>
      <SplitBar
        who={`Me (${money(q4.mine.fixed)} of ${money(q4.mine.total)})`}
        fixedShare={q4.mine.fixed_share}
        color="var(--pine)"
        tint="var(--pine-tint)"
      />
      <SplitBar
        who={`Comparable households (${money(q4.benchmark.fixed)} of ${money(q4.benchmark.total)}/yr)`}
        fixedShare={q4.benchmark.fixed_share}
        color="var(--graphite)"
        tint="#e5e4df"
      />
      <p className="caption">
        “Committed” = {q4.fixed_categories.join(", ").toLowerCase()} — a stated
        judgment call, not a standard definition.
      </p>
    </section>
  );
}
