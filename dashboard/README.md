# Spend dashboard (task 18)

One screen answering every question in `../questions.md`, rendered entirely
from `data/metrics.json` — the pipeline's precomputed output. No analysis
logic exists in this app (see `../decisions.md`, task 18 section).

## Run

```
cd dashboard
npm install
npm run dev        # http://localhost:3000
```

Regenerate the data after a pipeline rerun:

```
cd .. && .venv/bin/python export_dashboard_data.py
```

## Which data it shows

`METRICS_PATH` (absolute, or relative to `dashboard/`) selects the data file.
**The default is the synthetic sample** — a deploy that sets nothing, or is
misconfigured, serves demo data rather than real finances. Real data is the
explicit opt-in:

```
npm run dev                                   # synthetic sample (default)
METRICS_PATH=data/metrics.json npm run dev    # real, local only
```

`data/sample.metrics.json` is tracked and is what Vercel serves; everything
else in `data/` is gitignored. The page labels itself "Sample data" whenever
the loaded file carries `meta.dataset: "sample"`, so the label cannot be
forgotten and disappears on its own when pointed at real data.

Regenerate the sample (runs the whole pipeline over `../sample/`):

```
cd .. && .venv/bin/python build_sample.py
```

## Deploying (Vercel)

- **Root directory: `dashboard`** — the repo root is the Python pipeline.
- Framework preset: Next.js. Build `npm run build`, install `npm install`.
- **Set no environment variables.** `METRICS_PATH` must stay unset so the
  sample is used; pointing it at a real file would require that file to exist
  in the deployed bundle, which it never does.
- `next.config.ts` explicitly traces `data/sample.metrics.json` into the
  serverless bundle — the page reads it at request time from a path Next
  cannot infer statically, so without that entry the deploy 500s.

## Design

See `DESIGN.md` — palette, type, layout, and the checks it was held to.
