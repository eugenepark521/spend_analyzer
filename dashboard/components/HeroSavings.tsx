import type { Metrics } from "@/lib/metrics";
import { money, monthLabel, signedPct } from "@/lib/format";

export default function HeroSavings({ q1 }: { q1: Metrics["q1_savings"] }) {
  const { current, prior } = q1;
  // Direction is computed, never asserted: on some datasets the rate improves,
  // and a hardcoded "down from" would state the opposite of the numbers shown.
  const delta =
    current.rate !== null && prior.rate !== null ? current.rate - prior.rate : null;
  const word = delta === null ? "vs." : delta > 0 ? "up from" : delta < 0 ? "down from" : "level with";
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
          <span className={delta !== null && delta > 0 ? "hero-up" : "hero-down"}>
            {word} <strong>{signedPct(prior.rate)}</strong> in{" "}
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
