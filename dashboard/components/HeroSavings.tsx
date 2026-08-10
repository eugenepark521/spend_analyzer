import type { Metrics } from "@/lib/metrics";
import { money, monthLabel, signedPct } from "@/lib/format";

export default function HeroSavings({ q1 }: { q1: Metrics["q1_savings"] }) {
  const { current, prior } = q1;
  return (
    <div className="hero-tile">
      <span className="kicker">
        Savings rate · {monthLabel(current.start)}–{monthLabel(current.end)}
      </span>
      <div className="hero-figure">
        {current.rate !== null ? signedPct(current.rate) : "n/a"}
      </div>
      <p className="hero-sub">
        Income <strong>{money(current.income)}</strong>, spending{" "}
        <strong>{money(current.spend)}</strong> over the last six full months —{" "}
        {prior.rate !== null ? (
          <span className="hero-down">
            down from <strong>{signedPct(prior.rate)}</strong> in{" "}
            {monthLabel(prior.start)}–{monthLabel(prior.end)}
          </span>
        ) : (
          <span>no prior-window rate (income ≤ 0)</span>
        )}
        .
      </p>
    </div>
  );
}
