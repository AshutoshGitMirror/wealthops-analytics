# Screenshot guide

Screenshots are intentionally not committed. Regenerate the warehouse and capture the current
UI so the evidence matches the code and seed.

## Capture

```bash
make demo
make dashboard
# open http://localhost:8501
```

Use a 1440×900 or larger browser window. Keep the sidebar visible so filters and the synthetic
data notice are part of the evidence. Do not crop out the disclaimer.

## Suggested set

| File | Workspace | What it should show |
|---|---|---|
| `01-executive-overview.png` | Executive overview | Cards, NNA/asset trend and channel donut |
| `02-flows-and-channels.png` | Flows & channels | Flow bars, channel table, advice funnel |
| `03-advisor-book.png` | Advisor book | Quartile scatter, advisor table and drill-down |
| `04-client-cohorts.png` | Client cohorts | Retention heatmap, curves and segment mix |
| `05-data-quality.png` | Data quality | 43/43 pass, check table and manifest |
| `06-ask-the-data.png` | Ask the data | A question, its displayed SQL and result rows |

## Rules

- Capture the default seed (`42`) unless you label the seed in the accompanying text.
- Do not edit numbers, axes or labels in an image editor.
- If a chart is misleading, fix the caption/definition or the SQL first.
- Do not include a real name, firm, client identifier, API key or local filesystem path.
- Prefer PNG; keep file sizes modest for a repository or application pack.
- Add a short caption beside each image: what it shows, the seed and the synthetic-data caveat.

## Recommended caption pattern

> **Executive overview (synthetic seed 42).** Latest-month assets, NNA, fee-based share and
> client metrics from the generated warehouse. All data is fabricated; retention is a synthetic
> closure assumption and migration is a plan-created proxy.
