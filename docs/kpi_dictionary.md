# KPI dictionary

This document is the contract for the governed KPI views. If a dashboard number and this
document disagree, the document and the SQL should be fixed together before the number is
presented.

All figures are **synthetic**. Units are nominal INR unless a column name ends in `_pct`
or `_pp`. The dashboard converts INR to ₹ crore (₹1 Cr = ₹10,000,000) for display.

## Shared conventions

| Convention | Rule |
|---|---|
| Observation window | 24 month-ends, default 2024-11-30 → 2026-10-31. Monthly views use `month_start` (first day of the month) as their date key. |
| Month grain | One row per calendar month (or per month × channel / cohort / advisor, as stated). |
| Time zone | Dates only; no time-zone conversion. |
| Sign convention | Inflows are positive; outflows are negative in the fact table and positive in `outflows_inr` after sign reversal. |
| As-of attribution | Facts carry the advisor whose SCD2 interval covers the event date (transaction date, month-end or event date). |
| Missing denominators | Percentage views return NULL rather than dividing by zero. |
| Rounding | Views round percentages to two decimals where practical; dashboards display one decimal. |
| Synthetic labels | Every output is fabricated; planted relationships are assumptions, not causality. |

### What “fee-based” means

An account is fee-based when `ops.account.is_fee_based` is true. In the scenario these are
managed portfolios, advisory accounts and fee-based brokerage. Fee-based assets are the sum of
`total_assets_inr` for those accounts. Fee-based share is the ratio to all assets, not the share
of revenue.

### What “retained” means

A client is retained in month N after onboarding if they have a **positive total asset balance**
in that month. It is an asset-presence proxy. It is not product retention, revenue retention or
a contractual renewal measure.

### What “NNA” means

Net new assets = external client inflows (deposits + transfers in) minus external client
outflows (withdrawals + transfers out). Dividends, interest, fees, buys and sells are internal
movements and are excluded. NNA is therefore a **gross client-flow measure**, not investment
performance, revenue or AUM growth.

---

## 1. Monthly flows and NNA

**View:** `analytics.kpi_monthly_flows`

**Grain:** one row per month. **Unit:** INR; percentages in `_pct`.

| Column | Definition |
|---|---|
| `inflows_inr` | Sum of positive amounts where `is_net_new` is true. |
| `outflows_inr` | Absolute value of negative `is_net_new` amounts. |
| `net_new_assets_inr` | `inflows_inr − outflows_inr`; also the signed sum of net-new amounts. |
| `nna_check_inr` | Arithmetic check; must equal `net_new_assets_inr`. |
| `net_new_flow_count` | Count of net-new transactions. |
| `net_new_client_count` | Distinct clients with at least one net-new transaction. |
| `prior_month_nna_inr` | `LAG(net_new_assets_inr)` by month. |
| `nna_mom_change_inr` | Current NNA − prior-month NNA. |
| `nna_mom_pct` | 100 × change / prior-month NNA, or NULL when prior is NULL/zero. |
| `running_nna_inr` | Cumulative NNA from the first month in the view. |
| `nna_ytd_inr` | Cumulative NNA within the calendar year. |
| `nna_ltm_inr` | Sum of the current and previous 11 months; for the first months it is the available history, not a full year. |

**Filters:** none in the view; dashboard filters `month_start` between the selected months.

**Caveats**

- Excludes market growth and income; a rising book can coexist with negative NNA if outflows
  exceed inflows.
- `nna_ltm_inr` is a rolling sum of observed months. In the first 11 months it is a partial-year
  total, despite the name.
- The default scenario creates large initial funding deposits for accounts opened inside the
  window, so early months can show unusually large NNA.
- NNA is not attributed to investment performance and must not be added to market growth.

---

## 2. Flow-type detail

**View:** `analytics.kpi_flow_types`

**Grain:** one row per month × flow type × direction. **Unit:** INR and counts.

| Column | Definition |
|---|---|
| `flow_type` | `deposit`, `transfer_in`, `withdrawal`, `transfer_out`, `dividend`, `interest`, `fee`, `buy`, `sell`. |
| `direction` | `inflow`, `outflow` or `internal`. |
| `flow_count` | Number of transactions. |
| `client_count` | Distinct clients with that flow type. |
| `gross_amount_inr` | Signed sum of all amounts for the group. |
| `nna_inr` | Sum of amounts where `is_net_new`; zero for internal movement types. |

**Caveats:** `gross_amount_inr` includes internal movements and can offset; use `nna_inr` only
for the external-flow view. A flow type can appear in multiple directions in the raw data; the
grain is the pair, so group carefully.

---

## 3. Monthly assets and fee-based share

**View:** `analytics.kpi_monthly_assets`

**Grain:** one row per month. **Unit:** INR; percentages in `_pct`, percentage points in `_pp`.

| Column | Definition |
|---|---|
| `total_assets_inr` | Sum of account-month total balances. |
| `fee_based_assets_inr` | Sum of balances for accounts with `is_fee_based = true`. |
| `non_fee_based_assets_inr` | Total − fee-based. |
| `fee_based_share_pct` | 100 × fee-based assets / total assets; NULL if total is zero. |
| `estimated_fee_revenue_inr` | Synthetic monthly fee debited on fee-based accounts (fee-rate estimate, not billed revenue). |
| `clients_with_assets` | Distinct clients with a positive balance in the month. |
| `accounts_with_assets` | Distinct accounts with a positive balance in the month. |
| `avg_assets_per_client_inr` | Total assets / clients with assets; NULL if none. |
| `prior_month_assets_inr` | `LAG(total_assets_inr)`. |
| `assets_mom_pct` | 100 × month-over-month asset change / prior assets; NULL when prior is zero. |
| `fee_based_share_mom_pp` | Current fee share minus prior fee share, in percentage points. |
| `fee_based_share_3m_avg_pct` | Average fee share over the current and previous two months. |
| `inflows_inr`, `outflows_inr`, `net_new_assets_inr` | Joined from the monthly flows view for convenience. |
| `nna_ltm_inr` | Joined trailing-12-month NNA. |

**Caveats**

- Asset totals include market movement and internal income; do not describe them as NNA.
- `estimated_fee_revenue_inr` is a scenario estimate based on fee rates, not cash collected.
- Fee-based share can rise merely because fee-based accounts receive new funding or because
  non-fee balances fall; the view does not attribute the cause.

---

## 4. Channel mix

**View:** `analytics.kpi_channel_mix`

**Grain:** one row per month × acquisition channel. **Unit:** INR, counts, percentages.

| Column | Definition |
|---|---|
| `channel_name` / `channel_type` | Acquisition channel (`Digital Direct`, `Branch Network`, `Advisory & Private Client`). |
| `clients` | Distinct clients with positive assets in the month. |
| `accounts` | Distinct funded accounts. |
| `total_assets_inr` | Sum of balances for the channel. |
| `fee_based_assets_inr` | Fee-based balances in the channel. |
| `fee_based_share_pct` | 100 × channel fee-based assets / channel total assets. |
| `assets_share_pct` | 100 × channel assets / all-channel assets for the month. |
| `clients_share_pct` | 100 × channel clients / all-channel clients for the month. |
| `nna_inr` | Net new assets attributed to the channel in the month. |
| `nna_ltm_inr` | Rolling 12-month channel NNA. |

**Caveats**

- Channel is the client’s **acquisition** channel, not a product-holding, servicing or advice
  channel. A digital-acquired client can hold advisory products.
- Channel shares sum to 100% before rounding. Small deviations are display rounding.
- A channel can have negative NNA in a month because gross outflows exceed gross inflows.

---

## 5. Migration to advice (digital proxy)

**Views:** `analytics.kpi_migration_to_advice`, `analytics.kpi_migration_summary`

**Grain:** cohort month × channel for the detail view; one row per channel for the summary.
**Unit:** counts and percent.

**Definition**

- **Eligible:** client acquired through `DIGITAL`, onboarded on or before
  `max(month_end) − 90 days`.
- **Migrated:** eligible client with at least one engagement event of type `plan_created`.
- **Rate:** 100 × migrated / eligible; NULL if no eligible clients.

| Column (detail) | Definition |
|---|---|
| `cohort_month` | Month of onboarding. |
| `eligible_clients` | Eligible clients in the cohort. |
| `migrated_clients` | Eligible clients with a completed plan. |
| `not_migrated_clients` | Eligible − migrated. |
| `migration_rate_pct` | 100 × migrated / eligible. |
| `first_plan_date` | Earliest plan-created date in the cohort, if any. |

**Caveats**

- This is a **proxy milestone**, not a causal estimate of advice adoption, revenue conversion,
  product uptake or client satisfaction.
- The 90-day eligibility rule is a scenario convention.
- Events can occur before the 24-month asset window for pre-existing clients; the view uses the
  observation end from the asset fact table, not the first event date.
- A plan event is synthetic and has no quality, suitability or outcome meaning.
- Do not compare this rate to published industry conversion rates.

---

## 6. Cohort retention

**Views:** `analytics.kpi_cohort_retention`, `analytics.kpi_retention_summary`,
`analytics.kpi_advice_funnel` (journey context)

**Grain:** cohort month × months since onboarding. **Unit:** counts and percent.

| Column | Definition |
|---|---|
| `cohort_month` | Month of onboarding. |
| `cohort_size` | Clients in the cohort, regardless of whether they have assets in an observed month. |
| `months_since_onboarding` | 0–N, where N is the number of month boundaries in the asset window. |
| `retained_clients` | Distinct cohort clients with positive total assets in the corresponding month; NULL when the month is outside the observation window. |
| `retention_rate_pct` | 100 × retained / cohort size; NULL when unobserved. |
| `is_observed` | TRUE only when the cohort month + offset falls inside the observed month range. |

**Summary:** `kpi_retention_summary` uses the 12-month offset, only observed rows, and a
cohort-size-weighted rate: 100 × sum(retained) / sum(cohort size).

**12-month retention is month-level:** a client is counted as retained at 12 months when it
has positive assets in the 12th observed calendar month after its onboarding cohort month
(cohort_month + 12 months). This is not exact anniversary-day retention.

**Caveats**

- High retention is a **synthetic closure assumption**, not evidence of client loyalty.
- Retained means positive assets, not active, profitable, satisfied or still contracted.
- Clients can have zero assets in a month for reasons other than formal closure; the scenario
  retains a zero-balance closure month so flow and asset reconciliation still works.
- Unobserved future months are NULL, not zero; never average them as zero.
- Cohorts with limited history have fewer observed points. The dashboard and summary should not
  imply a full 24-month curve for recent cohorts.

---

## 7. Advisor productivity

**Views:** `analytics.kpi_advisor_productivity`, `analytics.kpi_advisor_monthly`,
`analytics.kpi_top_advisors`

**Grain:** one row per advisor (latest month) or advisor × month (trend). **Unit:** INR,
counts, percentages, rank/quartile integers.

| Column | Definition |
|---|---|
| `clients` / `accounts` | Funded clients/accounts attributed as of the latest month. |
| `total_assets_inr` | Latest-month assets in the advisor’s book. |
| `fee_based_assets_inr` / `fee_based_share_pct` | Fee-based balances and share. |
| `nna_ltm_inr` | Net new assets in the 12 months ending at the latest month, as-of attributed. |
| `plans_ltm` / `meetings_ltm` | Planning events and meetings in the same 12-month window. |
| `engagement_minutes_ltm` | Sum of engagement durations. |
| `estimated_fee_revenue_ltm` | Synthetic fee estimate over the trailing year. |
| `assets_per_client_inr` | Assets / clients; NULL if zero clients. |
| `nna_per_client_inr` | LTM NNA / clients. |
| `meetings_per_client` | LTM meetings / clients. |
| `pct_of_book` | 100 × advisor assets / all-advisor assets. |
| `nna_rank` | `RANK()` by LTM NNA descending; rank 1 is highest. |
| `productivity_quartile` | `NTILE(4)` by LTM NNA descending; **quartile 1 is the top quartile**. |
| `nna_gap_to_next_inr` | NNA minus the previous rank’s NNA; NULL for rank 1. |

**Caveats**

- NNA attribution follows the SCD2 assignment covering each flow date; a client transferred
  mid-year contributes to both books over time.
- Rank ties can share a rank; quartile buckets are balanced but can place equal values in
  different buckets. Do not use quartiles as a precise performance rating.
- Book size is deliberately uneven by scenario design.
- Meetings and plans are activity counts, not advice quality or outcomes.
- The view is a point-in-time snapshot; do not add it across months.

---

## 8. Client value, top-N and segments

**Views:** `analytics.kpi_client_value`, `analytics.kpi_top_clients`,
`analytics.kpi_client_segments`

**Grain:** one row per client (latest month), top 25 clients, or one row per segment.
**Unit:** INR, counts, percentages.

| Column | Definition |
|---|---|
| `total_assets_inr` | Latest-month total across the client’s accounts. |
| `fee_based_assets_inr` / `fee_based_share_pct` | Fee-based balances and share. |
| `nna_ltm_inr` | Client LTM net new assets. |
| `plans_ltm` / `meetings_ltm` / `has_plan` | Engagement activity in the trailing year and any plan flag. |
| `asset_rank` | `RANK()` by latest assets descending. |
| `asset_decile` | `NTILE(10)` by latest assets descending; decile 1 is the largest book. |
| `asset_percentile` | `PERCENT_RANK()` × 100. |
| `pct_of_book` | 100 × client assets / all-client assets. |
| `segment` | Synthetic wealth segment (`Emerging` … `Ultra HNI`). |

**Caveats**

- Top-N uses the latest month only; a client can appear or disappear between months.
- `kpi_client_value` includes clients with a latest-month snapshot, including zero-balance
  closure rows. `active_clients` in the executive view counts only positive balances.
- **Population coverage difference:** `kpi_client_value` covers clients present in the latest-month
  asset snapshot (4,750 clients; matched LTM NNA = ₹1,587.9 Cr in default seed). Total LTM NNA in
  `kpi_exec_overview` and `kpi_monthly_flows` includes all 5,000 clients (₹1,309.1 Cr), which includes
  250 closed clients who exited earlier in the trailing 12 months with ₹-278.9 Cr of net outflows.
  The two reconcile mathematically: matched book NNA (₹1,587.9 Cr) + departed client outflows
  (₹-278.9 Cr) = total warehouse NNA (₹1,309.1 Cr).
- Segment membership is synthetic and fixed at onboarding in this scenario.
- Do not treat the top 25 as a target list for real outreach.

---

## 9. Engagement and planning activity

**Views:** `analytics.kpi_engagement_monthly`, `analytics.kpi_engagement_summary`

**Grain:** month × event type (monthly) or month (summary). **Unit:** counts and minutes.

| Column | Definition |
|---|---|
| `events` | Number of engagement events. |
| `clients` / `engaged_clients` | Distinct clients with an event. |
| `advice_meetings` | Events of type `meeting`. |
| `plans_created` | Events of type `plan_created`. |
| `plan_reviews` | Events of type `plan_review`. |
| `avg_duration_minutes` / `total_minutes` | Average and total recorded duration. |
| `planning_events` | Events flagged as planning events. |

**Caveats**

- Events are synthetic activity records. They do not measure advice quality, suitability,
  client satisfaction or outcomes.
- Engagement history can include dates before the 24-month asset window for clients onboarded
  earlier; dashboard date filters limit the displayed range.
- A plan-created event drives the migration proxy; it is not a regulatory or product event.

---

## 10. Executive overview

**View:** `analytics.kpi_exec_overview`

**Grain:** exactly one row, as of the latest month in the asset fact. **Unit:** mixed.

| Field | Definition |
|---|---|
| `as_of_month` / `as_of_month_end` | Latest month start and month-end. |
| `total_assets_inr`, `fee_based_assets_inr`, `fee_based_share_pct` | From the latest monthly assets row. |
| `active_clients`, `active_accounts` | Distinct clients/accounts with positive assets. |
| `avg_assets_per_client_inr` | Latest assets / active clients. |
| `latest_month_nna_inr` | Latest month’s NNA. |
| `nna_ltm_inr`, `nna_ytd_inr` | Latest flow row’s rolling and year-to-date NNA. |
| `advisors` | Count of real synthetic advisors (excludes the unassigned placeholder). |
| `migration_rate_pct` | From `kpi_migration_summary`. |
| `retention_12m_pct` | From `kpi_retention_summary`. |
| `plans_created_ltm`, `advice_meetings_ltm`, `estimated_fee_revenue_ltm` | Trailing-year activity and fee estimate. |

**Caveats**

- The executive snapshot is not filtered by the dashboard date range; it is always the latest
  month. Trend charts do respond to filters.
- It is a convenience view, not a second source of truth. Tests assert consistency with the
  constituent views.

---

## 11. Data-quality result view

**View:** `analytics.v_data_quality`

**Grain:** one row per check in the latest run. **Unit:** text/status plus observed/expected
values.

| Column | Definition |
|---|---|
| `check_name` | Stable human-readable check name. |
| `category` | Uniqueness, referential integrity, SCD2, reconciliation, validity, invariants, reproducibility, etc. |
| `severity` | Scenario severity label. |
| `status` | `PASS` or `FAIL`. |
| `observed` / `expected` | Values that make the result inspectable. |
| `details` | What the check proves. |
| `checked_at` | Timestamp of the check run. |

**Caveats:** a green quality gate means the synthetic warehouse satisfies its stated
invariants. It does not validate real-world data quality or business truth.

---

## Definition quick-reference

| Question | Correct answer | Common mistake |
|---|---|---|
| Is NNA the same as AUM growth? | No. NNA excludes market movement and internal income. | Adding market growth to NNA. |
| Is fee-based share revenue share? | No. It is a balance share. | Calling it fee revenue share. |
| Is 99.5% retention a market benchmark? | No. It is a synthetic closure assumption. | Quoting it as a finding. |
| Is migration 17.2% an advice conversion rate? | No. It is a plan-created proxy for digital clients. | Comparing it to industry conversion. |
| Is the channel an advice channel? | No. It is the acquisition channel. | Treating digital clients as non-advised. |
| Does advisor rank measure advice quality? | No. It ranks trailing NNA. | Using it as a performance rating. |
