# User stories and acceptance criteria

Stories are written from the point of view of the people who would review or use the
workbench. Each story is small enough to verify and maps to a requirement in
[requirements.md](requirements.md) and to the evidence in the repository.

Status key: **Implemented** — the behaviour exists and is tested or directly exercised.

---

## US-01 — Reproduce the warehouse from one command

**As a** hiring reviewer, **I want** a single command that builds and validates the whole
warehouse, **so that** I can judge the project without assembling it by hand.

**Acceptance criteria**

- [x] `make demo` creates `.venv`, installs dependencies, resets the database, generates data,
  loads it, builds dimensions/facts/KPIs, runs the quality gate, exports CSVs and runs pytest.
- [x] Re-running `make demo` produces the same logical data (same seed).
- [x] A failure in any quality check or test stops the command with a non-zero exit code.
- [x] The README documents the prerequisites and the one-command path.

**Evidence:** `Makefile`, `src/wealthops/pipeline.py`; FR-16, FR-17.

---

## US-02 — Inspect a credible operational model

**As a** data engineer, **I want** normalised source tables with keys and constraints,
**so that** the analytics layer is built on something explainable.

**Acceptance criteria**

- [x] Clients, advisors, channels, accounts, transactions, snapshots, engagements and
  assignments live in the `ops` schema.
- [x] Primary keys are unique and foreign keys resolve.
- [x] Money columns are numeric INR; dates are `DATE`.
- [x] The data dictionary explains every table and column.

**Evidence:** `sql/01_operational_schema.sql`, `docs/data_dictionary.md`;
`tests/test_pipeline.py::test_duplicate_primary_keys_are_absent`; FR-02.

---

## US-03 — Use a star schema for analysis

**As a** BI developer, **I want** conformed dimensions and fact tables, **so that** KPI SQL is
simple and consistent.

**Acceptance criteria**

- [x] Dimensions exist for date, client, advisor, channel and account.
- [x] Facts exist for flows, monthly assets and engagement.
- [x] Fact rows reconcile one-for-one to their operational source rows.
- [x] Fact-to-dimension joins are tested.

**Evidence:** `sql/10_dimensions.sql`, `sql/20_facts.sql`,
`tests/test_pipeline.py::test_fact_row_counts_reconcile`; FR-03.

---

## US-04 — Attribute history to the right advisor

**As an** analytics engineer, **I want** SCD2 advisor assignments with an as-of join,
**so that** a transaction is credited to the advisor who owned the client on that date.

**Acceptance criteria**

- [x] Each client has non-overlapping assignment intervals and exactly one current row.
- [x] `effective_to` is inclusive; a NULL `effective_to` means current.
- [x] Every flow, asset snapshot and engagement fact resolves to the assignment covering its
  event date, with zero mismatches.
- [x] A current-assignment helper view covers every client.

**Evidence:** `sql/10_dimensions.sql`, `sql/20_facts.sql`,
`tests/test_scd2.py`; FR-04.

---

## US-05 — Trust the numbers through a quality gate

**As a** risk-minded reviewer, **I want** explicit checks with observed and expected values,
**so that** I can see what “green” actually means.

**Acceptance criteria**

- [x] At least 40 checks cover uniqueness, referential integrity, SCD2, reconciliation,
  validity, seeded invariants and reproducibility.
- [x] Every check returns `PASS` on the default seed.
- [x] The CLI displays the pass count and fails on any non-`PASS` status.
- [x] Checks are parameter-aware for a smaller test fixture.

**Evidence:** `sql/quality/checks.sql`, `tests/test_pipeline.py::test_quality_checks_all_pass`;
FR-19.

---

## US-06 — Read NNA correctly

**As a** business analyst, **I want** NNA defined as external inflows minus external outflows,
**so that** I do not confuse client flows with market growth or revenue.

**Acceptance criteria**

- [x] Deposits and transfers in add to NNA; withdrawals and transfers out subtract.
- [x] Dividends, interest, fees, buys and sells are excluded.
- [x] Monthly inflows, outflows and NNA reconcile to the flow fact.
- [x] Running, YTD and trailing-12-month NNA are calculated with window functions and tested.
- [x] The KPI dictionary states the grain, unit, filters and caveats.

**Evidence:** `sql/30_kpi_flows.sql`, `docs/kpi_dictionary.md`,
`tests/test_kpi_math.py`; FR-07.

---

## US-07 — Track the shift to fee-based assets

**As a** business analyst, **I want** fee-based assets and their share of the book,
**so that** I can describe the mix shift without implying causation.

**Acceptance criteria**

- [x] Fee-based assets are the balances of accounts flagged fee-based.
- [x] Share = fee-based assets / total assets × 100, with a null-safe zero denominator.
- [x] The monthly view includes prior-month change and a three-month average.
- [x] The dashboard shows the trend and the definition.

**Evidence:** `sql/31_kpi_assets.sql`,
`tests/test_kpi_math.py::test_monthly_assets_reconcile_and_fee_share_formula`; FR-08.

---

## US-08 — Compare acquisition channels

**As a** sales analyst, **I want** client, asset and NNA mix by acquisition channel,
**so that** I can describe where the book comes from.

**Acceptance criteria**

- [x] Each channel has monthly clients, accounts, assets, fee share, asset share and NNA.
- [x] Asset shares sum to 100% per month within rounding.
- [x] Channel NNA reconciles to the flow fact and includes a 12-month rolling value.
- [x] The dashboard shows the latest mix and allows channel filtering.

**Evidence:** `sql/32_kpi_channel.sql`,
`tests/test_kpi_math.py::test_channel_mix_shares_and_nna_reconcile`; FR-09.

---

## US-09 — Measure migration to advice honestly

**As a** strategy analyst, **I want** a documented digital-client migration proxy,
**so that** I can discuss adoption without overstating causality or conversion.

**Acceptance criteria**

- [x] Eligible clients are digital-acquired and onboarded at least 90 days before the
  observation end.
- [x] Migrated clients have at least one `plan_created` engagement event.
- [x] The summary equals the sum of cohort rows; the rate uses the documented denominator.
- [x] The dashboard labels the metric as a synthetic milestone/proxy.

**Evidence:** `sql/33_kpi_migration.sql`,
`tests/test_kpi_math.py::test_migration_summary_matches_cohorts_and_definition`; FR-10.

---

## US-10 — Review retention by onboarding cohort

**As a** client-analytics analyst, **I want** cohort retention with months since onboarding,
**so that** I can see the shape of asset persistence over time.

**Acceptance criteria**

- [x] Cohort = month of onboarding.
- [x] Retained = positive total assets in the observation month.
- [x] Observed months are flagged; unobserved future months are NULL rather than zero.
- [x] The 12-month summary is weighted by cohort size.
- [x] The dashboard shows a heatmap and curves and discloses the synthetic closure assumption.

**Evidence:** `sql/34_kpi_retention.sql`,
`tests/test_kpi_math.py::test_retention_rates_and_observed_flags`; FR-11.

---

## US-11 — Compare advisor productivity fairly

**As a** sales manager (simulated), **I want** rank and quartiles based on trailing NNA,
**so that** I can compare advisors without hiding the definition.

**Acceptance criteria**

- [x] Rank 1 is the highest LTM NNA; quartile 1 is the top quartile.
- [x] The view includes book size, assets per client, fee share, meetings, plans and book share.
- [x] Book shares sum to 100% and quartiles are deterministic.
- [x] The dashboard supports an advisor drill-down.

**Evidence:** `sql/35_kpi_advisors.sql`,
`tests/test_kpi_math.py::test_advisor_rank_and_quartiles`; FR-12.

---

## US-12 — Find top clients and segments

**As a** relationship manager (simulated), **I want** top-N clients and segment mix,
**so that** I can prioritise coverage discussions.

**Acceptance criteria**

- [x] Clients are ranked by latest total assets with deciles and percentiles.
- [x] Top clients are limited to the top 25 by rank.
- [x] Segment shares and fee shares are computed from the latest month.
- [x] Findings are labelled synthetic and non-causal.

**Evidence:** `sql/36_kpi_clients.sql`,
`tests/test_kpi_math.py::test_client_rankings_and_segments`; FR-13.

---

## US-13 — Give an executive a one-screen answer

**As an** executive, **I want** a consistent snapshot of assets, NNA, fee mix, clients,
migration and retention, **so that** I can start from one trusted row.

**Acceptance criteria**

- [x] `kpi_exec_overview` returns exactly one row for the latest month.
- [x] Its asset, flow, migration and retention fields equal the corresponding KPI views.
- [x] The dashboard shows cards and trends with metric definitions and caveats.
- [x] The snapshot is labelled synthetic.

**Evidence:** `sql/38_kpi_exec.sql`,
`tests/test_kpi_math.py::test_executive_overview_is_consistent`; FR-14.

---

## US-14 — Ask a question without breaking the warehouse

**As a** demo user, **I want** to ask a plain-English question and see the SQL,
**so that** I can explore governed metrics without write access.

**Acceptance criteria**

- [x] Example prompts run offline through deterministic rules and return rows.
- [x] Unknown questions fail with guidance instead of guessing.
- [x] Generated SQL is allow-listed, single-statement, SELECT-only and wrapped in a row limit.
- [x] The executed SQL is displayed; execution uses a read-only connection.
- [x] Adversarial attempts (DROP, DELETE, PRAGMA, ATTACH, COPY, raw tables, comments,
  multi-statement, file functions) are rejected with tests.

**Evidence:** `src/wealthops/nlq/`, `tests/test_nlq.py`; FR-21–FR-25.

---

## Cross-cutting acceptance

- [x] `.env` is gitignored; no API key or secret is committed.
- [x] Dashboard and README carry the synthetic-data/no-affiliation notice.
- [x] `docs/screenshots/` explains how to capture evidence without editing numbers.
- [x] README limitations disclose high retention, proxy migration, fixed window and demo-only
  NLQ scope.
