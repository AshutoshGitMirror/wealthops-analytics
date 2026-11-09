# WealthOps Analytics

A runnable, end-to-end **synthetic wealth-management analytics workbench** built around
SQL-first KPI reporting, a DuckDB warehouse, Python automation and a Streamlit dashboard.
It is a portfolio project for a wealth-management / analytics apprenticeship application —
not a product, not a real firm and not a source of real client data.

> **Synthetic data notice.** Every client, advisor, balance, transaction, engagement event
> and outcome in this repository is fabricated by a seeded generator. There is **no Morgan
> Stanley affiliation** and **no real, confidential or client data** anywhere in the project.
> Planted relationships are scenario assumptions, not causal findings or market estimates.

## What it demonstrates

- A **normalised operational schema** plus a **star-schema analytics layer**.
- **SCD Type 2 advisor assignments** with an as-of join used by every fact table.
- A deterministic generator with an explicit seed, manifest and logical fingerprints.
- **43 data-quality checks** that run as a release gate in the pipeline and the test suite.
- **124 pytest tests** covering pipeline reconciliation, KPI mathematics, SCD2 intervals,
  generator determinism, the NL-query guard, dedicated CLI suite, and the dashboard data/UI layers.
- Governed KPI views for NNA, fee-based assets, channel mix, migration-to-advice,
  retention cohorts, advisor productivity, client value, engagement and an executive snapshot.
- A **read-only Streamlit dashboard** with six workspaces and filter-aware charts.
- An optional **NL-to-SQL assistant** that is allow-listed, SELECT-only, wrapped in a row
  limit and executed on a read-only connection. The deterministic rules engine works offline.
- Documentation written for a reviewer: requirements, user stories, KPI dictionary,
  architecture, data dictionary and an AI-usage disclosure.

## Quick start

Prerequisites: Python 3.11+, GNU Make, and roughly 2 GB of free RAM. The project was built
and tested on a 2-core / 8 GB Linux laptop.

```bash
git clone https://github.com/AshutoshGitMirror/wealthops-analytics.git
cd wealthops-analytics

make setup       # create .venv and install the pinned runtime + dev extras
make demo        # generate data, build DuckDB, run 43 checks, export CSVs, run tests
make dashboard   # http://localhost:8501
```

`make demo` is the one-command acceptance path. It performs a reset build, so it is safe to
re-run. To build without the test run:

```bash
make build
```

To run only the warehouse quality gate:

```bash
make quality
.venv/bin/wealthops status
```

### DuckDB version pin

`duckdb==1.1.3` is pinned deliberately. DuckDB 2.x crashed with `SIGILL` on the AVX-only
CPU used to develop this project. The pin keeps the quickstart reproducible on that machine.
On a newer CPU you may experiment with a newer DuckDB, but re-run `make demo` first.

## Default scenario

| Parameter | Value |
|---|---|
| Seed | `42` (override with `--seed` / `WEALTHOPS_SEED`) |
| Clients | 5,000 |
| Advisors | 30 |
| Acquisition channels | 3 (`Digital Direct`, `Branch Network`, `Advisory & Private Client`) |
| Observation window | 24 month-ends, 2024-11-30 → 2026-10-31 |
| Currency / units | nominal INR; dashboard displays ₹ crore (₹1 Cr = ₹10,000,000) |

Default build scope: 8,674 accounts, 214,287 transactions, 148,331 account-month snapshots,
36,137 engagement events and 5,820 SCD2 assignments. These are synthetic scenario counts,
not a claim about any real business.

### Headline snapshot from the default seed

All figures below are **synthetic** and exist to demonstrate definitions, not to benchmark a
market. They will change if the seed or scenario size changes.

| Metric | Default output |
|---|---|
| Assets under analytics (latest month) | ≈ ₹60,936 Cr |
| Fee-based asset share | ≈ 61.2% |
| Active clients / funded accounts | 4,617 / 8,008 |
| NNA, trailing twelve months | ≈ ₹1,309 Cr |
| Latest-month NNA | ≈ ₹263 Cr |
| Digital migration to advice | ≈ 17.2% |
| 12-month cohort retention | ≈ 99.5% |

**The retention figure is high because the synthetic closure process is an assumption, not
because the project discovered unusually sticky clients.** The generator gives most clients
a low closure probability and treats “retained” as “positive asset balance at month N”. See
[Honest limitations](#honest-limitations).

## Dashboard

Run `make dashboard` and open <http://localhost:8501>. The six workspaces are:

1. **Executive overview** — assets, NNA, fee-based share, active clients, retention, migration,
   flow and asset trends, top-advisor NNA.
2. **Flows & channels** — inflow/outflow bars, channel mix, advice funnel, flow-type detail
   and migration cohorts.
3. **Advisor book** — book size, LTM NNA, quartiles, assets per client, meetings/plans and an
   advisor trend drill-down.
4. **Client cohorts** — retention heatmap and curves, segment mix, top clients by latest assets.
5. **Data quality** — pass/fail table, warehouse counts and the scenario manifest.
6. **Ask the data** — governed example questions and a single-question NL query box that
   displays the SQL it executed.

The dashboard opens short-lived **read-only** DuckDB connections and reads governed views.
Dates filter monthly views. Channel filters apply to channel views; segment filters apply to
client views. The executive snapshot is as of the latest month and is intentionally not
date-filtered; the trend charts respond to the selected window.

### Screenshots

Screenshots are not committed because the dashboard is meant to be regenerated from the
seeded data. Capture them after `make demo`:

```bash
make dashboard
# then capture each workspace at 1440×900 or larger
```

Suggested files for an application pack:

- `docs/screenshots/01-executive-overview.png`
- `docs/screenshots/02-flows-and-channels.png`
- `docs/screenshots/03-advisor-book.png`
- `docs/screenshots/04-client-cohorts.png`
- `docs/screenshots/05-data-quality.png`
- `docs/screenshots/06-ask-the-data.png`

Do not edit a screenshot to change a number. If a chart is confusing, fix the definition or
the caption first. See [docs/screenshots/README.md](docs/screenshots/README.md).

## Governed natural-language querying

The assistant is deliberately narrow: it is a demonstration of **governed access**, not a
general text-to-SQL product. It only reads curated `analytics.*` views.

```bash
make nlq QUESTION="Show net new assets by month"
.venv/bin/wealthops nlq "Compare the latest channel mix" --show-sql
```

Controls:

- allow-listed views only;
- one `SELECT` / `WITH ... SELECT` statement;
- DDL, DML, `PRAGMA`, `ATTACH`, `COPY`, comments, comma joins, file/table functions and
  string-literal `FROM` targets are rejected;
- an outer `LIMIT` is always applied;
- `UNION` / `UNION ALL` between SELECTs on allowlisted views is permitted because it
  remains a single read-only statement; every source must still be allowlisted;
- execution uses a read-only DuckDB connection;
- the deterministic keyword rules engine is the default and works offline;
- an optional OpenAI-compatible endpoint can be enabled with
  `WEALTHOPS_LLM_API_KEY` / `WEALTHOPS_LLM_BASE_URL` / `WEALTHOPS_LLM_MODEL`.
  Model output still passes the same guard. No key is committed or logged.

Adversarial guard cases are covered in `tests/test_nlq.py`.

## Data quality gate

`sql/quality/checks.sql` defines 43 checks. They cover:

- primary-key uniqueness and referential integrity;
- non-negative balances and valid dates;
- SCD2 interval overlap, gaps, current-row count and as-of attribution;
- asset recurrence and flow-to-snapshot reconciliation;
- fact-to-operational row-count reconciliation;
- seeded scenario invariants (counts, channel ordering, fee-share / migration / retention ranges);
- manifest consistency.

The pipeline fails if any check is not `PASS`:

```bash
make quality
# [quality] 43/43 checks passed
```

The checks read the scenario size from `ops.scenario_config`, so the smaller pytest fixture
(1,200 clients) is validated against its own declared counts rather than hard-coded 5,000.

## Project layout

```text
.
├── dashboard/app.py              # Streamlit UI
├── docs/                         # requirements, stories, KPI and data dictionaries
├── exports/                      # generated CSV marts (gitignored)
├── sql/
│   ├── 01_operational_schema.sql
│   ├── 02_load_operational.sql
│   ├── 10_dimensions.sql
│   ├── 20_facts.sql
│   ├── 30_kpi_flows.sql ... 38_kpi_exec.sql
│   └── quality/checks.sql
├── src/wealthops/
│   ├── config.py                 # scenario settings and paths
│   ├── generate.py               # deterministic synthetic generator
│   ├── pipeline.py               # generate → load → transform → quality → export
│   ├── cli.py                    # wealthops command
│   ├── dashboard/data.py         # read-only dashboard queries
│   └── nlq/                      # guard, rules, optional LLM, engine
├── tests/                        # 105 pytest tests
├── Makefile
├── pyproject.toml
└── requirements.txt
```

Generated artefacts (`data/*.duckdb`, parquet files, manifests, `exports/*.csv`) are
gitignored and reproducible from the seed.

## Documentation map

| Document | What it answers |
|---|---|
| [docs/requirements.md](docs/requirements.md) | Scope, users, functional/non-functional requirements, acceptance criteria |
| [docs/user_stories.md](docs/user_stories.md) | 14 user stories with testable acceptance criteria |
| [docs/kpi_dictionary.md](docs/kpi_dictionary.md) | Definition, grain, units, filters and caveats for every KPI |
| [docs/architecture.md](docs/architecture.md) | Data flow, schemas, SCD2, as-of joins, security and failure modes |
| [docs/data_dictionary.md](docs/data_dictionary.md) | Tables, columns, keys, view grains and units |
| [docs/ai_usage.md](docs/ai_usage.md) | How AI was used, what is generated, controls and limits |
| [docs/resume_bullets.md](docs/resume_bullets.md) | Resume bullet templates with placeholders for measured results |
| [docs/screenshots/README.md](docs/screenshots/README.md) | Screenshot guidance and naming |

## Testing

```bash
make test
.venv/bin/python -m pytest -q
```

The suite builds a 1,200-client warehouse once per session, then verifies:

- manifest counts, operational/fact reconciliation and exports;
- NNA, LTM/YTD/running windows, fee share, channel shares, migration, retention,
  advisor quartiles and executive consistency;
- SCD2 non-overlap/gaps and as-of attribution for every fact row;
- generator determinism and seed sensitivity;
- guard adversarial cases, CTE/UNION allowlist enforcement, and the rules engine;
- dashboard helper queries, app compilation, and automated headless simulation of all six workspace renders via Streamlit `AppTest`.

To run tests without rebuilding the test database fixture repeatedly:
```bash
.venv/bin/python -m pytest
```

## Reviewer Walkthrough & Acceptance Guide

This project is designed for straightforward evaluation by technical reviewers. All client data, advisor books, account balances, and interactions are completely synthetic and deterministic.

### 1. One-Command Acceptance Run
```bash
make demo
```
This runs the full release gate in sequential order:
1. `setup`: prepares the Python virtual environment and installs pinned dependencies.
2. `build`: drops local databases, runs the deterministic generator (seed 42), loads parquet files into DuckDB operational tables (`ops.*`), builds the dimensional warehouse and 18 KPI views (`analytics.*`), executes the 43 data-quality checks, and exports 12 CSV reporting marts.
3. `test`: executes all 123 pytest unit and integration tests against an isolated temporary test warehouse.

### 2. Launching and Navigating the Dashboard
```bash
make dashboard
```
Open [http://localhost:8501](http://localhost:8501) in your browser to inspect the six analytical workspaces:
* **Executive overview:** Review headline metrics (Assets Under Analytics, Fee-based Share %, LTM NNA, 12-Month Cohort Retention %, Digital Migration Rate %), monthly flow trajectories, asset breakdown, and top-advisor rankings.
* **Flows & channels:** Explore gross inflows vs outflows, net new assets by channel, the multi-stage digital advice funnel, and flow-type distributions.
* **Advisor book:** Inspect advisor productivity quartiles (`NTILE(4)`), client/account distributions per advisor, and drill down into individual advisor monthly asset trends.
* **Client cohorts:** Examine onboarding cohort retention matrices over elapsed tenure, retention decay curves, and wealth segment asset concentrations.
* **Data quality:** Review the live audit trail of all 43 automated data-quality checks, warehouse row-count reconciliations, and the cryptographic scenario manifest.
* **Ask the data:** Test the governed natural-language query engine. Click example questions or enter queries to observe the allowlisted SQL executed on a read-only DuckDB connection.

### 3. Sample Questions for "Ask the data"
Try entering these questions in the Ask the data workspace (or via CLI `.venv/bin/wealthops nlq "<question>" --show-sql`):
* `Show net new assets by month`
* `Compare the latest channel mix`
* `Show advisor productivity quartiles`
* `What is the 12-month cohort retention rate?`
* `Show top 10 advisors by LTM NNA`

### 4. Key SQL Files to Inspect
* [`sql/10_dimensions.sql`](sql/10_dimensions.sql): Dimensional modeling and SCD Type 2 dimension `analytics.dim_advisor_assignment`.
* [`sql/20_facts.sql`](sql/20_facts.sql): As-of event-date joins resolving historical advisor assignment via `BETWEEN aa.effective_from AND COALESCE(aa.effective_to, DATE '9999-12-31')`.
* [`sql/30_kpi_flows.sql`](sql/30_kpi_flows.sql): Rolling 12-month analytical window functions (`ROWS BETWEEN 11 PRECEDING AND CURRENT ROW`).
* [`sql/35_kpi_advisors.sql`](sql/35_kpi_advisors.sql): Advisor productivity quartiles (`NTILE(4)`) and league rankings.
* [`sql/36_kpi_clients.sql`](sql/36_kpi_clients.sql): Client deciles (`NTILE(10)`), percentiles (`PERCENT_RANK()`), and book percentages.
* [`sql/quality/checks.sql`](sql/quality/checks.sql): 43-check data quality validation suite covering referential integrity, interval bounds, balance recurrence, and scenario invariants.

## Honest limitations

1. **All data is synthetic.** Conclusions transfer to nothing in the real world.
2. **Retention is high by construction.** Most clients are never closed; “retained” means
   “positive assets at month N”. Do not present 99.5% as a market retention benchmark.
3. **Migration is a proxy milestone.** It uses a completed `plan_created` event and a 90-day
   eligibility rule. It is not advice conversion, revenue conversion or a causal estimate.
4. **NNA is a flow measure, not performance.** Market growth, fees, dividends and trades are
   deliberately excluded from NNA.
5. **Channel is acquisition channel.** It is not a product-holding or servicing measure.
6. **Advisor assignments are synthetic.** SCD2 mechanics are realistic; the people and books
   are fabricated and deliberately uneven.
7. **The scenario window is fixed in this release.** The default SQL and dashboard assume the
   window ending 2026-10-31. The generator settings expose dates, but a different window would
   require reviewing views that reference the observation boundary.
8. **NLQ is a narrow demo.** The rules engine recognises a curated set of questions. The
   optional LLM is not a required dependency and is not evaluated for accuracy or safety
   beyond the guard.
9. **No production concerns are solved here:** authentication, row-level security, PII,
   lineage, orchestration, observability, cost controls and a real data contract are out of
   scope.
10. **Dashboard performance is laptop-scale.** DuckDB is configured for 2 threads and 2 GB;
    the marts are small by design.

## Resume bullet template

Static technical facts are fine; **measured impact must be filled in from real measurements,
never invented**. Replace bracketed values only after you have measured them.

- Built a synthetic wealth-management analytics workbench with Python, SQL, DuckDB and
  Streamlit covering `[N]` clients and `[M]` transactions, with a seeded generator and a
  reproducible one-command build.
- Modelled a normalised operational schema and star-schema marts with SCD2 advisor
  assignments and as-of joins; validated the warehouse with `[N]` automated data-quality
  checks.
- Defined and tested `[N]` KPI views (NNA, fee-based share, channel mix, migration, cohort
  retention, advisor productivity) with documented grain, units and caveats.
- Implemented a guarded NL-to-SQL layer over read-only analytics views; blocked `[N]`
  adversarial statement classes and kept the deterministic offline fallback.
- Delivered a six-page Streamlit dashboard with filters, metric definitions and an
  executive view; reduced time-to-answer for `[task]` from `[before]` to `[after]`
  (only if actually measured).

## Security and ethics

- No secrets are committed; `.env` is gitignored. `.env.example` contains no key.
- All generated names are generic (`Client 000001`, `Advisor 01`).
- The project name and documentation explicitly disclaim any firm affiliation.
- The NL assistant is allow-listed and read-only; it is still a demo and is not a security
  boundary for untrusted users on a shared production system.

## License

MIT. See `pyproject.toml` for the package metadata.
