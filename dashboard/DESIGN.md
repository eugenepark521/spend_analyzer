# Dashboard design plan (task 18)

Concept: **an audit, not a pitch.** Two years of one household's spending,
measured against comparable households, with the honest negatives stated
plainly. The page should read like a signed-off report: quiet surfaces, one
authoritative accent, provenance visible.

## Palette (6 named values)

| Name | Hex | Role |
|---|---|---|
| paper | `#f3f2ed` | page plane |
| card | `#fcfcfb` | panel surface |
| ink | `#16211c` | text; the hero tile's fill (green-cast near-black) |
| pine | `#006b41` | my data — the only saturated hue on the page |
| graphite | `#898781` | benchmark/context marks, muted text |
| claret | `#b3372c` | negative/over — text and delta chips only |

Validated with the dataviz skill's `validate_palette.js` (light surface
`#fcfcfb`): pine passes the lightness band, chroma floor, contrast (5.9:1),
and its pair with graphite clears CVD ΔE 13.6 (target ≥8) and normal-vision
ΔE 19.0 (floor ≥15). Graphite intentionally fails the chroma floor: it is the
de-emphasis gray of the skill's *emphasis* form (my data in one hue,
benchmark in gray), never a second categorical hue — identity is carried by
the legend and direct labels, not by graphite's hue. Claret is a status
color: it appears only as text/delta with a sign, never as a mark adjacent
to pine (avoids red–green adjacency). Text contrasts: ink/card 16.1:1,
claret/card 5.9:1, white/ink-tile 14.5:1, all ≥ 4.5:1.

## Type

- **Display** — Archivo (700, tight tracking): page title, panel headings, hero figure.
- **Body** — Inter: labels, captions, copy.
- **Data** — IBM Plex Mono: the provenance/meta line, axis ticks, table numerals
  (`tabular-nums`). Mono carries the "audit trail" voice; used small, never for prose.

## Layout (one laptop screen)

```
┌ title ──────────────────────────────── meta (mono) ┐
├ hero: savings tile (ink) ┬ month strip (signature) ┤
├──────────────────────────┴─────────────────────────┤
│ Q3 spending vs comparable      │ Q2 budget (90d)   │
│ households — paired bars,      ├───────────────────┤
│ 14 categories, tall left       │ Q4 fixed  │ Q5 0- │
│ (the panel a hiring manager    │ vs flex   │ state │
│ reads first)                   ├───────────────────┤
│                                │ Q7 volatility     │
│                                ├───────────────────┤
│                                │ Q6 no-forecast    │
└────────────────────────────────┴───────────────────┘
```

Below ~1000px the grid stacks to one column (the one-screen bar applies to
laptop, not phone).

## Signature element

**The month strip**: every coverage month as a paired income (graphite) /
spend (pine) bar, with partial-coverage months rendered as hollow slots at the
ends — the data-coverage caveat made visible instead of footnoted. It spans the
hero band and is the thing the page is remembered by. (Monthly savings *rate*
bars were rejected: when income arrives in lumps a single thin month produces a
rate in the thousands of percent, which flattens every other bar; income-vs-
spend pairs tell the same story at an honest scale.)

## Checks against the brief

- Not cream+serif+terracotta (sans display, green accent), not
  near-black+acid (light page, one dark tile, deep-not-neon accent), not
  broadsheet hairline columns (card grid, no column rules).
- Boldness spent in exactly one place: the ink hero tile with the −% savings
  figure. Everything else is quiet.
- Copy is meaning-first: "Spending vs. comparable households", not "BLS CEX
  reconciliation"; "Nothing unusual this month — 0 of N flagged", not
  "empty result set".
- Every number renders from `metrics.json` (env-swappable path); no analysis
  and no constants in components.
- Charts follow the dataviz skill: emphasis form (pine + graphite), one axis
  everywhere, thin marks with surface gaps, selective direct labels, legends
  for two-series charts, tooltips never the only path to a value (each chart
  panel has a screen-reader table), no animation (respects reduced motion by
  default), visible keyboard focus.
