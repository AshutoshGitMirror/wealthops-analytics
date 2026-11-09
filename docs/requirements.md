# Requirements

## 1. Purpose

WealthOps Analytics is a portfolio-grade, runnable demonstration of the analytical work a
wealth-management apprentice or junior analyst might do: turn an operational client/account
dataset into governed KPIs, investigate flows and cohorts, automate the warehouse build, test
the definitions, and present findings to a business audience.

The project is **synthetic by design**. It must never imply access to real client data or an
affiliation with any wealth-management firm.

## 2. Users and jobs

| User | Job to be done |
|---|---|
| Hiring reviewer | Clone the repo, run one command, inspect a credible analytics workflow and the reasoning behind it. |
| Business analyst | Answer “what changed in NNA, fee-based share, channel mix, migration and retention?” without writing ad-hoc SQL each time. |
| Data/analytics engineer | Inspect the schema, SCD2 logic, reconciliation checks, reproducibility and security posture. |
| Advisor / sales manager (simulated) | Compare book size, NNA and productivity quartiles and drill into one advisor. |
| Risk-minded reviewer | Try to break the NL assistant and confirm it cannot read raw tables or mutate the database. |

## 3. Scope

### In scope

- A seeded synthetic wealth-management scenario with clients, advisors, channels, accounts,
  transactions, monthly asset snapshots, engagement events and SCD2 advisor assignments.
- A normalised operational layer and a star-schema analytics layer.
- Governed KPI views with documented definitions.
- A quality gate, CSV exports and a Streamlit dashboard.
- An optional, guarded natural-language query assistant.
- Documentation sufficient for an independent reviewer to judge the work.

### Out of scope

- Real client data, PII, production authentication or row-level security.
- Real market data, performance attribution, trading, billing or regulatory reporting.
- Cloud deployment, orchestration, streaming, a feature store or a production scheduler.
- Causal inference, forecasting or model performance claims.
- A general-purpose text-to-SQL product.
- Morgan Stanley branding, claims or affiliation of any kind.

## 4. Functional requirements

### Data and model

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Generate deterministic synthetic data from an explicit seed. | Two runs with the same settings produce identical logical fingerprints; a different seed changes them. |
| FR-02 | Produce a normalised operational schema with primary and foreign keys. | Tables exist in `ops`; PK uniqueness and FK validity are tested. |
| FR-03 | Produce a star-schema analytics layer with client, advisor, channel, account and date dimensions and flow, monthly-asset and engagement facts. | All dimensions/facts exist; fact row counts reconcile to their operational source. |
| FR-04 | Model advisor assignment as SCD Type 2 with effective dates and a current flag. | No overlaps or gaps; exactly one current assignment per client; facts use the assignment covering the event date. |
| FR-05 | Keep the scenario size in a manifest and configuration table. | Quality checks read `ops.scenario_config`; the 1,200-client test fixture passes without changing SQL constants. |
| FR-06 | Label synthetic data prominently in the manifest, dashboard and docs. | Disclaimer appears in the manifest, dashboard header and README; names are generic. |

### KPIs

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-07 | Define NNA as external inflows minus external outflows, excluding internal income, fees and trades. | `kpi_monthly_flows` reconciles to the fact table; tests verify the definition and running/LTM/YTD windows. |
| FR-08 | Report fee-based assets and their share of total assets by month. | Fee assets sum from fee-based accounts; share = fee assets / total assets × 100; tests verify the formula. |
| FR-09 | Report channel mix by clients, assets, fee share and NNA. | Per-month asset shares sum to 100% within rounding; channel NNA reconciles to flows. |
| FR-10 | Define a migration-to-advice proxy for digital clients. | Eligibility and `plan_created` logic are documented; summary equals cohort sums and the re-derived eligible/migrated counts. |
| FR-11 | Report cohort retention with an explicit observed/unobserved flag. | Rate = retained / cohort size × 100; only observed months are summarised; 12-month summary is weighted. |
| FR-12 | Report advisor productivity, rank and quartiles with window functions. | Quartile 1 is the highest trailing-12-month NNA; ranks and quartiles are computed deterministically; book share sums to 100%. |
| FR-13 | Report top-N clients, segments and engagement activity. | Window-function ranks/deciles are present; segment asset shares sum to 100%; engagement views reconcile. |
| FR-14 | Provide a one-row executive snapshot. | It equals the latest month’s asset and flow KPIs, migration summary and retention summary. |
| FR-15 | Document every KPI’s grain, unit, filters and caveats. | `docs/kpi_dictionary.md` covers every governed view used by the dashboard or assistant. |

### Pipeline and operations

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-16 | Provide CLI/Make targets for generate, load, transform, quality, export, build, status, reset. | `wealthops --help` and `make help` list the commands; `make demo` completes. |
| FR-17 | Make the build one-command and repeatable. | `make demo` resets the database, rebuilds, runs the quality gate and tests from a clean checkout. |
| FR-18 | Export governed marts for Excel/BI use. | Twelve CSVs are written to `exports/` and are non-empty. |
| FR-19 | Fail the pipeline on any quality failure. | `wealthops quality` and `wealthops build` exit non-zero when a check fails. |
| FR-20 | Provide a dashboard with executive, flow/channel, advisor, cohort, quality and NLQ workspaces. | All six pages render against the built warehouse without an exception. |

### NL query and security

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-21 | Allow only single SELECT/WITH statements over allow-listed analytics views. | Guard rejects DDL/DML/PRAGMA/ATTACH/COPY, comments, multiple statements, unknown tables and unqualified views. |
| FR-22 | Force a row limit and read-only execution. | Every accepted query is wrapped in an outer LIMIT and runs on a read-only connection. |
| FR-23 | Provide a deterministic offline fallback. | The rules engine answers the example prompts with no API key and returns the same SQL for the same question. |
| FR-24 | Make the optional LLM strictly optional and guarded. | Without a key no network call is made; model output passes the same guard before execution. |
| FR-25 | Display the SQL and the security controls to the user. | The dashboard shows the executed SQL, source (rules/LLM) and allow-list. |

### Documentation and evidence

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-26 | Document requirements, stories, KPI dictionary, architecture, data dictionary and AI usage. | All six documents exist and agree with the implemented schema/views. |
| FR-27 | Provide at least ten user stories with acceptance criteria. | `docs/user_stories.md` contains 14 stories mapped to requirements and tests. |
| FR-28 | Provide a screenshot guide without committing fabricated evidence. | `docs/screenshots/README.md` gives reproducible capture instructions. |
| FR-29 | Provide a resume bullet template with placeholders for measured results only. | README template contains no invented impact numbers. |
| FR-30 | Avoid secrets and commit-ready artefacts. | `.env` is gitignored; `.env.example` has no key; raw data, database and exports are gitignored. |

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | Runs on Python 3.11+ with a lightweight local install. |
| NFR-02 | Works on a 2-core / ~8 GB laptop; DuckDB uses 2 threads and a 2 GB memory limit. |
| NFR-03 | Default build uses modest data volumes (5,000 clients; ~214k transactions) and completes in minutes, not hours. |
| NFR-04 | Deterministic by seed; no wall-clock or unseeded randomness in the scenario data. |
| NFR-05 | SQL is a first-class artefact; business logic lives in `sql/`, not hidden in Python strings. |
| NFR-06 | The dashboard is read-only and queries governed views, never raw operational tables. |
| NFR-07 | The test suite is independent of the developer’s local `data/` directory (it builds a temp fixture). |
| NFR-08 | Outputs are clearly labelled as synthetic; no real names, firms or client identifiers. |
| NFR-09 | Failures are visible: quality checks print observed vs expected; tests fail on any red check. |
| NFR-10 | The project is clone-and-run with no manual data download and no required API key. |

## 6. Data and definition assumptions

1. The observation window is 24 complete months ending 2026-10-31.
2. All monetary values are nominal INR. The dashboard converts to ₹ crore for display only.
3. NNA excludes dividends, interest, fees and buy/sell trades; those are internal movements.
4. Fee-based accounts are managed portfolios, advisory accounts and fee-based brokerage.
5. Fee revenue is a synthetic estimate (fee rate applied to balances), not billed revenue.
6. A client is “retained” in a month if they have a positive total asset balance.
7. A digital client is “migrated” if they were onboarded at least 90 days before the
   observation end and had at least one `plan_created` event.
8. Advisor quartile 1 is the highest trailing-12-month NNA.
9. Planted relationships are assumptions for demonstration, not causal claims.
10. The synthetic closure process produces high retention; this must be disclosed wherever
    retention is presented.

## 7. Acceptance scenario

A reviewer should be able to:

1. Clone the repository on a clean machine with Python 3.11+.
2. Run `make demo` and see a green quality gate (`43/43`) and a green test suite (`105 passed`).
3. Run `make dashboard`, open the six workspaces and see consistent numbers.
4. Run `make nlq QUESTION="Show net new assets by month"` and inspect the generated SQL.
5. Read the KPI dictionary and explain the difference between NNA, asset growth and revenue.
6. Try an unsafe NLQ statement (for example `DROP TABLE ops.client`) and see it rejected.
7. Read the limitations and understand which numbers are synthetic assumptions.

## 8. Traceability

| Requirement group | Evidence |
|---|---|
| FR-01–FR-06 | `src/wealthops/generate.py`, `sql/01_operational_schema.sql`, `sql/10_dimensions.sql`, `tests/test_generator.py`, `tests/test_pipeline.py` |
| FR-07–FR-15 | `sql/30_kpi_flows.sql` … `sql/38_kpi_exec.sql`, `docs/kpi_dictionary.md`, `tests/test_kpi_math.py` |
| FR-16–FR-19 | `src/wealthops/pipeline.py`, `src/wealthops/cli.py`, `Makefile`, `sql/quality/checks.sql` |
| FR-20 | `dashboard/app.py`, `src/wealthops/dashboard/data.py`, `tests/test_dashboard.py` |
| FR-21–FR-25 | `src/wealthops/nlq/`, `tests/test_nlq.py` |
| FR-26–FR-30 | `README.md`, `docs/`, `.gitignore`, `.env.example` |
