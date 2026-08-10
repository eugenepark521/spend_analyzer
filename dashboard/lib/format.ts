// Presentation-only formatting. Never math beyond display rounding.
export const money = (n: number, digits = 0) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const moneyCompact = (n: number) =>
  Math.abs(n) >= 10_000
    ? `$${(n / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })}k`
    : money(n);

export const pct = (n: number, digits = 1) => `${n.toFixed(digits)}%`;

export const signedPp = (n: number) =>
  `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(1)}pp`;

export const signedPct = (n: number) =>
  `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(1)}%`;

// "2026-01" -> "Jan 26" (labels), "2026-01-31" -> "Jan 31, 2026"
export const monthLabel = (ym: string) => {
  const [y, m] = ym.split("-").map(Number);
  return `${"JFMAMJJASOND"[m - 1]}${["an","eb","ar","pr","ay","un","ul","ug","ep","ct","ov","ec"][m - 1]} ’${String(y).slice(2)}`;
};

export const dateLabel = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${names[m - 1]} ${d}, ${y}`;
};
