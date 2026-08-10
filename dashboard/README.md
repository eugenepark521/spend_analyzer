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

## Swappable data path

`METRICS_PATH` (absolute, or relative to `dashboard/`) selects the data file;
default is the real `data/metrics.json`. Task 19 deploys against a synthetic
sample with the same schema:

```
METRICS_PATH=data/sample.metrics.json npm run dev
```

## Design

See `DESIGN.md` — palette, type, layout, and the checks it was held to.
