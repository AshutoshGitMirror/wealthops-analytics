# Data dictionary

All data is synthetic. Monetary columns are nominal INR unless stated otherwise. Boolean
columns are DuckDB `BOOLEAN`; keys are strings unless marked integer/bigint. “Grain” means what
one row represents. For KPI definitions and caveats see [kpi_dictionary.md](kpi_dictionary.md).

## 1. Operational schema (`ops`)

The operational layer is normalised and keyed by business identifiers. It is loaded from
`data/raw/*.parquet` by `sql/02_load_operational.sql`. The dashboard does not query it directly.

### `ops.channel`

**Grain:** one row per acquisition channel.

| Column | Type | Meaning |
|---|---|---|
| `channel_id` | INTEGER | Primary key. |
| `channel_code` | VARCHAR | `DIGITAL`, `BRANCH`, `ADVISORY`. |
| `channel_name` | VARCHAR | Display name (`Digital Direct`, `Branch Network`, `Advisory & Private Client`). |
| `channel_type` | VARCHAR | `Digital`, `Branch`, `Advisor-led`. |

### `ops.advisor`

**Grain:** one row per synthetic advisor.

| Column | Type | Meaning |
|---|---|---|
| `advisor_id` | VARCHAR | Primary key (`ADV01`…). |
| `advisor_name` | VARCHAR | Generic synthetic name. |
| `region` | VARCHAR | Mumbai, Pune, Bengaluru, Delhi NCR, Hyderabad. |
| `segment_specialty` | VARCHAR | Synthetic specialty. |
| `hire_date` | DATE | Synthetic hire date. |
| `status` | VARCHAR | Synthetic employment status. |

### `ops.client`

**Grain:** one row per synthetic client.

| Column | Type | Meaning |
|---|---|---|
| `client_id` | VARCHAR | Primary key (`CL000001`…). |
| `client_name` | VARCHAR | Generic synthetic name (`Client 000001`). |
| `channel_id` | INTEGER | FK → `ops.channel`. Acquisition channel. |
| `segment` | VARCHAR | Emerging, Mass Affluent, Affluent, HNI, Ultra HNI. |
| `risk_profile` | VARCHAR | Conservative, Moderate, Growth, Aggressive. |
| `city` | VARCHAR | Synthetic city. |
| `onboarding_date` | DATE | Client start date; can precede the 24-month asset window. |
| `status` | VARCHAR | Active, Dormant or Closed. |
| `closed_date` | DATE | Null unless closed; closure date can be mid-month. |

### `ops.account`

**Grain:** one row per account.

| Column | Type | Meaning |
|---|---|---|
| `account_id` | VARCHAR | Primary key (`AC…`). |
| `client_id` | VARCHAR | FK → `ops.client`. |
| `account_type` | VARCHAR | Synthetic account/product type. |
| `opened_date` | DATE | Account opening date. |
| `status` | VARCHAR | Synthetic account status. |
| `fee_rate_bps` | INTEGER | Synthetic annual fee rate in basis points. |
| `is_fee_based` | BOOLEAN | Included in fee-based assets and fee estimate. |

### `ops.advisor_assignment`

**Grain:** one SCD2 interval per client × advisor assignment. `effective_to` is inclusive;
NULL means current.

| Column | Type | Meaning |
|---|---|---|
| `assignment_id` | VARCHAR | Primary key (`AA…`). |
| `client_id` | VARCHAR | FK → `ops.client`. |
| `advisor_id` | VARCHAR | FK → `ops.advisor`. |
| `effective_from` | DATE | First date the advisor owns the client. |
| `effective_to` | DATE | Last date (inclusive); NULL = current. |
| `assignment_reason` | VARCHAR | Synthetic reason (onboarding, transfer, etc.). |
| `is_current` | BOOLEAN | Exactly one true row per client. |

### `ops.transaction`

**Grain:** one transaction.

| Column | Type | Meaning |
|---|---|---|
| `transaction_id` | VARCHAR | Primary key (`TX…`). |
| `account_id` | VARCHAR | FK → `ops.account`. |
| `client_id` | VARCHAR | FK → `ops.client` (denormalised for loading). |
| `channel_id` | INTEGER | FK → `ops.channel`. |
| `transaction_date` | DATE | Event date. |
| `transaction_type` | VARCHAR | deposit, transfer_in, withdrawal, transfer_out, dividend, interest, fee, buy, sell. |
| `direction` | VARCHAR | inflow, outflow, internal. |
| `amount_inr` | DOUBLE | Signed amount; inflows positive, outflows negative, internal signed as recorded. |
| `is_net_new` | BOOLEAN | True only for external deposits/transfers/withdrawals. |
| `is_fee_based` | BOOLEAN | Account fee flag at transaction time. |

### `ops.monthly_asset_snapshot`

**Grain:** one account × month-end.

| Column | Type | Meaning |
|---|---|---|
| `snapshot_id` | VARCHAR | Primary key (`MS…`). |
| `account_id` | VARCHAR | FK → `ops.account`. |
| `client_id` | VARCHAR | FK → `ops.client`. |
| `month_end` | DATE | Month-end date. |
| `beginning_assets_inr` | DOUBLE | Opening balance. |
| `market_growth_inr` | DOUBLE | Synthetic market movement. |
| `net_new_assets_inr` | DOUBLE | External net flows in the month. |
| `internal_income_inr` | DOUBLE | Dividends/interest. |
| `fee_amount_inr` | DOUBLE | Synthetic fee debit. |
| `market_return_pct` | DOUBLE | Synthetic monthly return. |
| `market_value_inr` | DOUBLE | Market value component. |
| `cash_balance_inr` | DOUBLE | Cash component. |
| `total_assets_inr` | DOUBLE | Ending total; recurrence identity documented below. |

Recurrence: `total_assets_inr = beginning_assets_inr + market_growth_inr +
net_new_assets_inr + internal_income_inr − fee_amount_inr`.

### `ops.engagement_event`

**Grain:** one client engagement event.

| Column | Type | Meaning |
|---|---|---|
| `event_id` | VARCHAR | Primary key (`EV…`). |
| `client_id` | VARCHAR | FK → `ops.client`. |
| `advisor_id` | VARCHAR | Advisor at event time. |
| `channel_id` | INTEGER | Client acquisition channel. |
| `event_date` | DATE | Event date; may precede the asset window for early clients. |
| `event_type` | VARCHAR | meeting, call, digital_login, plan_created, plan_review, etc. |
| `duration_minutes` | INTEGER | Synthetic duration. |
| `is_planning_event` | BOOLEAN | True for plan-created/review events. |

### `ops.scenario_config`

**Grain:** one row per declared scenario parameter. Used by quality checks.

| Key | Meaning |
|---|---|
| `expected_clients` | Declared client count. |
| `expected_advisors` | Declared advisor count. |
| `expected_channels` | Declared channel count. |
| `expected_months` | Declared observation months. |
| `expected_min_transactions` | Minimum expected transaction volume (`max(1000, clients × 10)`). |
| `seed` | Seed used for the build. |

## 2. Analytics dimensions

### `analytics.dim_date`

**Grain:** one row per day, 2023-01-01 → 2026-12-31. `date_key` is `YYYYMMDD`.

| Column | Type | Meaning |
|---|---|---|
| `date_key` | INTEGER | Surrogate date key. |
| `date` | DATE | Calendar date. |
| `year`, `quarter`, `month` | INTEGER | Calendar parts. |
| `month_name` | VARCHAR | Short month name. |
| `month_start`, `month_end` | DATE | Month boundaries. |
| `year_month` | VARCHAR | `YYYY-MM`. |
| `is_month_end` | BOOLEAN | True on the last day of a month. |

### `analytics.dim_channel`

**Grain:** one row per channel. `channel_key = channel_id`.

| Column | Type | Meaning |
|---|---|---|
| `channel_key` | INTEGER | Surrogate key. |
| `channel_id` | INTEGER | Operational key. |
| `channel_code`, `channel_name`, `channel_type` | VARCHAR | Attributes. |

### `analytics.dim_advisor`

**Grain:** one row per advisor plus an `advisor_key = 0` “Unassigned” member.

| Column | Type | Meaning |
|---|---|---|
| `advisor_key` | BIGINT | Surrogate key; 0 = unassigned. |
| `advisor_id`, `advisor_name`, `region`, `segment_specialty` | VARCHAR | Attributes. |
| `hire_date` | DATE | Hire date. |
| `status` | VARCHAR | Status. |

### `analytics.dim_client`

**Grain:** one row per client.

| Column | Type | Meaning |
|---|---|---|
| `client_key` | BIGINT | Surrogate key. |
| `client_id`, `client_name` | VARCHAR | Business key and generic name. |
| `channel_key` | INTEGER | FK → `dim_channel`. |
| `channel_code`, `channel_name` | VARCHAR | Acquisition channel attributes. |
| `segment`, `risk_profile`, `city` | VARCHAR | Attributes. |
| `onboarding_date` | DATE | Client start date. |
| `cohort_month` | DATE | First day of the onboarding month. |
| `status`, `closed_date` | VARCHAR / DATE | Client status and closure. |
| `is_active` | BOOLEAN | True unless status is `Closed`. |
| `tenure_months` | BIGINT | Months from onboarding to the fixed observation end (2026-10-31). |

### `analytics.dim_account`

**Grain:** one row per account.

| Column | Type | Meaning |
|---|---|---|
| `account_key` | BIGINT | Surrogate key. |
| `account_id` | VARCHAR | Business key. |
| `client_key` | BIGINT | FK → `dim_client`. |
| `account_type`, `status` | VARCHAR | Attributes. |
| `opened_date` | DATE | Opening date. |
| `fee_rate_bps` | INTEGER | Fee rate. |
| `is_fee_based` | BOOLEAN | Fee-based flag. |
| `account_age_days` | BIGINT | Days from opening to the fixed observation end. |

### `analytics.dim_advisor_assignment`

**Grain:** one SCD2 interval.

| Column | Type | Meaning |
|---|---|---|
| `assignment_key` | BIGINT | Surrogate key. |
| `client_key`, `advisor_key` | BIGINT | Dimension FKs. |
| `assignment_id` | VARCHAR | Operational key. |
| `effective_from`, `effective_to` | DATE | Inclusive interval; NULL end = current. |
| `is_current` | BOOLEAN | Current interval flag. |
| `assignment_reason` | VARCHAR | Synthetic reason. |
| `duration_days` | BIGINT | Effective-from to effective-to (or observation end). |

### `analytics.v_client_current_advisor`

**Grain:** one row per client with its current assignment. Joins `dim_client`,
`dim_advisor_assignment` (current) and `dim_advisor`.

Columns: `client_key`, `client_id`, `client_name`, `segment`, `channel_name`, `advisor_key`,
`advisor_name`, `region`, `effective_from`, `assignment_reason`.

## 3. Analytics facts

### `analytics.fact_flows`

**Grain:** one row per operational transaction. Keys: `flow_key`; business key
`transaction_id`.

| Column | Type | Meaning |
|---|---|---|
| `flow_key` | BIGINT | Surrogate key. |
| `transaction_id` | VARCHAR | Source transaction. |
| `date_key`, `flow_date`, `month_start` | INTEGER / DATE | Date dimensions. |
| `client_key`, `account_key`, `advisor_key`, `channel_key` | keys | Conformed dimensions; as-of advisor. |
| `flow_type`, `direction` | VARCHAR | Transaction type and direction. |
| `is_net_new`, `is_fee_based` | BOOLEAN | Flow/fee flags. |
| `amount_inr` | DOUBLE | Signed INR amount. |

### `analytics.fact_monthly_assets`

**Grain:** one row per operational account-month snapshot. Keys: `monthly_asset_key`;
business key `snapshot_id`.

| Column | Type | Meaning |
|---|---|---|
| `monthly_asset_key` | BIGINT | Surrogate key. |
| `snapshot_id` | VARCHAR | Source snapshot. |
| `month_date_key`, `month_end`, `month_start` | INTEGER / DATE | Date dimensions. |
| `client_key`, `account_key`, `advisor_key`, `channel_key` | keys | Conformed dimensions; as-of advisor at month-end. |
| `beginning_assets_inr`, `market_growth_inr`, `net_new_assets_inr`, `internal_income_inr`, `fee_amount_inr` | DOUBLE | Recurrence components. |
| `market_return_pct` | DOUBLE | Synthetic return. |
| `market_value_inr`, `cash_balance_inr`, `total_assets_inr` | DOUBLE | Ending balances. |
| `estimated_fee_revenue_inr` | DOUBLE | Same as fee amount for the month. |
| `fee_rate_bps`, `is_fee_based` | INTEGER / BOOLEAN | Account attributes at snapshot time. |

### `analytics.fact_engagement`

**Grain:** one row per operational engagement event. Keys: `engagement_key`; business key
`event_id`.

| Column | Type | Meaning |
|---|---|---|
| `engagement_key` | BIGINT | Surrogate key. |
| `event_id` | VARCHAR | Source event. |
| `date_key`, `event_date`, `month_start` | INTEGER / DATE | Date dimensions. |
| `client_key`, `advisor_key`, `channel_key` | keys | Conformed dimensions; as-of advisor at event date. |
| `event_type` | VARCHAR | Event type. |
| `duration_minutes` | INTEGER | Duration. |
| `is_planning_event` | BOOLEAN | Planning flag. |

## 4. KPI and quality views

Full definitions, units, filters and caveats are in [kpi_dictionary.md](kpi_dictionary.md).
This table is the quick inventory.

| View | Grain | Columns (summary) |
|---|---|---|
| `kpi_monthly_flows` | month | `month_start`, `calendar_year`, `inflows_inr`, `outflows_inr`, `net_new_assets_inr`, `nna_check_inr`, flow/client counts, `prior_month_nna_inr`, `nna_mom_change_inr`, `nna_mom_pct`, `running_nna_inr`, `nna_ytd_inr`, `nna_ltm_inr` |
| `kpi_flow_types` | month × flow_type × direction | `flow_count`, `client_count`, `gross_amount_inr`, `nna_inr` |
| `kpi_monthly_assets` | month | total/fee/non-fee assets, `fee_based_share_pct`, `estimated_fee_revenue_inr`, clients/accounts with assets, averages, prior/change/3m average, joined flow and LTM NNA |
| `kpi_channel_mix` | month × channel | clients, accounts, assets, fee assets/share, asset/client share, monthly and LTM NNA |
| `kpi_migration_to_advice` | cohort month × channel | eligible, migrated, not migrated, rate, first plan date |
| `kpi_migration_summary` | channel | eligible, migrated, rate, latest cohort |
| `kpi_advice_funnel` | channel | clients, engaged, planned, fee-based, rates |
| `kpi_cohort_retention` | cohort month × months since onboarding | cohort size, retained clients, rate, observed flag |
| `kpi_retention_summary` | one row | 12-month eligible/retained/rate |
| `kpi_advisor_productivity` | advisor | clients, accounts, assets, fee share, LTM NNA, plans/meetings/minutes, fee estimate, per-client metrics, book share, rank, quartile, gap |
| `kpi_advisor_monthly` | advisor × month | clients, assets, fee assets, NNA, prior assets, running NNA, assets rank |
| `kpi_top_advisors` | top 10 advisors | all productivity columns where `nna_rank <= 10` |
| `kpi_client_value` | client, latest month | accounts, assets, fee share, LTM NNA, plans/meetings, has-plan, rank, decile, percentile, book share |
| `kpi_top_clients` | top 25 clients | client-value columns where `asset_rank <= 25` |
| `kpi_client_segments` | segment | clients, accounts, assets, fee share, asset share, average assets, LTM NNA |
| `kpi_engagement_monthly` | month × event type | events, clients, average/total minutes, planning events |
| `kpi_engagement_summary` | month | events, engaged clients, meetings, plans, reviews, minutes |
| `kpi_exec_overview` | one row, latest month | assets, fee share, active clients/accounts, average assets, latest/LTM/YTD NNA, advisors, migration, retention, LTM plans/meetings/fees |
| `v_data_quality` | one row per check | check name, category, severity, status, observed, expected, details, checked_at |

## 5. Keys and lineage

| Analytics relation | Source | Key relationship |
|---|---|---|
| `dim_date` | Generated calendar | `date_key = YYYYMMDD` |
| `dim_channel` | `ops.channel` | `channel_key = channel_id` |
| `dim_advisor` | `ops.advisor` | `advisor_key`; 0 = Unassigned |
| `dim_client` | `ops.client` + `ops.channel` | `client_key`; `channel_key` FK |
| `dim_account` | `ops.account` + `dim_client` | `account_key`; `client_key` FK |
| `dim_advisor_assignment` | `ops.advisor_assignment` + `dim_client` + `dim_advisor` | `assignment_key`; client/advisor FKs |
| `fact_flows` | `ops.transaction` + date/account/client/assignment | `flow_key`; business key `transaction_id` |
| `fact_monthly_assets` | `ops.monthly_asset_snapshot` + date/account/client/assignment | `monthly_asset_key`; business key `snapshot_id` |
| `fact_engagement` | `ops.engagement_event` + date/client/assignment | `engagement_key`; business key `event_id` |

## 6. Known ranges and fixed assumptions

- `dim_date` covers 2023-01-01 → 2026-12-31. Engagement facts can include pre-window events for
  clients onboarded earlier; the dashboard filters the displayed range.
- `tenure_months` and `account_age_days` are computed to the fixed observation end 2026-10-31.
- The default observation window is 24 months ending 2026-10-31. A different window requires
  reviewing those fixed boundaries. This is documented as a limitation.
- IDs are synthetic and sequential within a table; they are not meaningful business numbers.
- `advisor_key = 0` is a reserved “Unassigned” member. The scenario expects no fact row to need
  it, and tests assert as-of attribution has no mismatches.
- Percentage columns are 0–100, not fractions.
- `INR` amounts are nominal and unrounded in the warehouse; CSV/dashboard display rounds.
