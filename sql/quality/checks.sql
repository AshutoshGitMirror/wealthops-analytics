-- Data-quality checks executed after the analytics build.
-- Each row has a boolean status so the CLI, tests and dashboard read the same
-- source of truth.  observed/expected are strings for display; numeric checks
-- can still be compared in tests by status.

CREATE OR REPLACE TABLE ops.dq_check_results AS
SELECT *, now() AS checked_at FROM (
    SELECT 'client_pk_unique' AS check_name, 'Uniqueness' AS category, 'error' AS severity,
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status,
           CAST(COUNT(*) AS VARCHAR) AS observed, '0' AS expected,
           'Duplicate client_id values in ops.client' AS details
    FROM (SELECT client_id FROM ops.client GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'account_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate account_id values in ops.account'
    FROM (SELECT account_id FROM ops.account GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'advisor_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate advisor_id values in ops.advisor'
    FROM (SELECT advisor_id FROM ops.advisor GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'transaction_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate transaction_id values'
    FROM (SELECT transaction_id FROM ops.transaction GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'snapshot_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate snapshot_id values'
    FROM (SELECT snapshot_id FROM ops.monthly_asset_snapshot GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'assignment_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate assignment_id values'
    FROM (SELECT assignment_id FROM ops.advisor_assignment GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'event_pk_unique', 'Uniqueness', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Duplicate event_id values'
    FROM (SELECT event_id FROM ops.engagement_event GROUP BY 1 HAVING COUNT(*) > 1)

    UNION ALL
    SELECT 'account_client_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Accounts without a client'
    FROM ops.account a LEFT JOIN ops.client c ON c.client_id = a.client_id
    WHERE c.client_id IS NULL

    UNION ALL
    SELECT 'transaction_account_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Transactions without an account'
    FROM ops.transaction t LEFT JOIN ops.account a ON a.account_id = t.account_id
    WHERE a.account_id IS NULL

    UNION ALL
    SELECT 'snapshot_account_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Snapshots without an account'
    FROM ops.monthly_asset_snapshot s LEFT JOIN ops.account a ON a.account_id = s.account_id
    WHERE a.account_id IS NULL

    UNION ALL
    SELECT 'assignment_client_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Assignments without a client'
    FROM ops.advisor_assignment aa LEFT JOIN ops.client c ON c.client_id = aa.client_id
    WHERE c.client_id IS NULL

    UNION ALL
    SELECT 'assignment_advisor_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Assignments without an advisor'
    FROM ops.advisor_assignment aa LEFT JOIN ops.advisor a ON a.advisor_id = aa.advisor_id
    WHERE a.advisor_id IS NULL

    UNION ALL
    SELECT 'event_client_fk', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Engagement events without a client'
    FROM ops.engagement_event e LEFT JOIN ops.client c ON c.client_id = e.client_id
    WHERE c.client_id IS NULL

    UNION ALL
    SELECT 'fact_flow_orphans', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'fact_flows rows with unknown dimension keys'
    FROM analytics.fact_flows f
    LEFT JOIN analytics.dim_client c ON c.client_key = f.client_key
    LEFT JOIN analytics.dim_account a ON a.account_key = f.account_key
    WHERE c.client_key IS NULL OR a.account_key IS NULL

    UNION ALL
    SELECT 'fact_asset_orphans', 'Referential integrity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'fact_monthly_assets rows with unknown dimension keys'
    FROM analytics.fact_monthly_assets f
    LEFT JOIN analytics.dim_client c ON c.client_key = f.client_key
    LEFT JOIN analytics.dim_account a ON a.account_key = f.account_key
    WHERE c.client_key IS NULL OR a.account_key IS NULL

    UNION ALL
    SELECT 'nonnegative_balances', 'Validity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Negative balances, cash or market values'
    FROM ops.monthly_asset_snapshot
    WHERE beginning_assets_inr < 0 OR total_assets_inr < 0
       OR market_value_inr < 0 OR cash_balance_inr < 0

    UNION ALL
    SELECT 'scd2_no_overlaps', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Overlapping advisor assignment intervals'
    FROM analytics.dim_advisor_assignment a
    JOIN analytics.dim_advisor_assignment b
      ON b.client_key = a.client_key AND b.assignment_key > a.assignment_key
     AND a.effective_from <= COALESCE(b.effective_to, DATE '9999-12-31')
     AND b.effective_from <= COALESCE(a.effective_to, DATE '9999-12-31')

    UNION ALL
    SELECT 'scd2_one_current', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Clients without exactly one current advisor assignment'
    FROM (
        SELECT client_key FROM analytics.dim_advisor_assignment
        GROUP BY 1 HAVING COUNT(*) FILTER (WHERE is_current) <> 1
    )

    UNION ALL
    SELECT 'scd2_current_is_latest', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Current interval is not the latest interval'
    FROM (
        SELECT client_key,
               MAX(effective_from) AS max_from,
               MAX(CASE WHEN is_current THEN effective_from END) AS current_from
        FROM analytics.dim_advisor_assignment
        GROUP BY 1
        HAVING current_from IS NULL OR current_from <> max_from
    )

    UNION ALL
    SELECT 'scd2_valid_intervals', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'effective_to is before effective_from'
    FROM analytics.dim_advisor_assignment
    WHERE effective_to IS NOT NULL AND effective_to < effective_from

    UNION ALL
    SELECT 'scd2_no_gaps', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Gaps between consecutive assignment intervals'
    FROM (
        SELECT client_key, effective_from,
               LAG(effective_to) OVER (PARTITION BY client_key ORDER BY effective_from) AS prior_to
        FROM analytics.dim_advisor_assignment
    ) x
    WHERE prior_to IS NOT NULL AND date_diff('day', prior_to, effective_from) > 1

    UNION ALL
    SELECT 'asset_recurrence', 'Reconciliation', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0',
           'Snapshot does not satisfy beginning + growth + NNA + income - fee = total'
    FROM ops.monthly_asset_snapshot
    WHERE ABS(beginning_assets_inr + market_growth_inr + net_new_assets_inr
              + internal_income_inr - fee_amount_inr - total_assets_inr) > 0.01

    UNION ALL
    SELECT 'flows_reconcile_to_monthly_nna', 'Reconciliation', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0',
           'Monthly snapshot NNA does not equal external transaction sum'
    FROM (
        SELECT account_id, date_trunc('month', transaction_date)::DATE AS month_start,
               SUM(amount_inr) AS nna
        FROM ops.transaction WHERE is_net_new GROUP BY 1, 2
    ) f
    FULL OUTER JOIN (
        SELECT account_id, date_trunc('month', month_end)::DATE AS month_start,
               SUM(net_new_assets_inr) AS nna
        FROM ops.monthly_asset_snapshot GROUP BY 1, 2
    ) s USING (account_id, month_start)
    WHERE ABS(COALESCE(f.nna, 0) - COALESCE(s.nna, 0)) > 0.01

    UNION ALL
    SELECT 'fact_assets_reconcile', 'Reconciliation', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0',
           'Fact monthly assets do not reconcile to operational snapshots'
    FROM (
        SELECT month_end, SUM(total_assets_inr) AS total FROM analytics.fact_monthly_assets GROUP BY 1
    ) f
    FULL OUTER JOIN (
        SELECT month_end, SUM(total_assets_inr) AS total FROM ops.monthly_asset_snapshot GROUP BY 1
    ) s USING (month_end)
    WHERE ABS(COALESCE(f.total, 0) - COALESCE(s.total, 0)) > 0.01

    UNION ALL
    SELECT 'fact_flows_row_count', 'Reconciliation', 'error',
           CASE WHEN COUNT(*) = (SELECT COUNT(*) FROM ops.transaction) THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), CAST((SELECT COUNT(*) FROM ops.transaction) AS VARCHAR),
           'fact_flows must have one row per transaction (as-of join must not multiply rows)'
    FROM analytics.fact_flows

    UNION ALL
    SELECT 'fact_engagement_row_count', 'Reconciliation', 'error',
           CASE WHEN COUNT(*) = (SELECT COUNT(*) FROM ops.engagement_event) THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), CAST((SELECT COUNT(*) FROM ops.engagement_event) AS VARCHAR),
           'fact_engagement must have one row per event (as-of join must not multiply rows)'
    FROM analytics.fact_engagement

    UNION ALL
    SELECT 'unassigned_flow_advisor', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Flow facts with no matching advisor interval'
    FROM analytics.fact_flows WHERE advisor_key = 0

    UNION ALL
    SELECT 'unassigned_asset_advisor', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Asset facts with no matching advisor interval'
    FROM analytics.fact_monthly_assets WHERE advisor_key = 0

    UNION ALL
    SELECT 'unassigned_event_advisor', 'SCD2', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Engagement facts with no matching advisor interval'
    FROM analytics.fact_engagement WHERE advisor_key = 0

    UNION ALL
    SELECT 'transaction_date_range', 'Validity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Transactions outside the observation window'
    FROM ops.transaction
    WHERE transaction_date < DATE '2024-11-01' OR transaction_date > DATE '2026-10-31'

    UNION ALL
    SELECT 'account_open_after_onboarding', 'Validity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Account opened before client onboarding'
    FROM ops.account a JOIN ops.client c ON c.client_id = a.client_id
    WHERE a.opened_date < c.onboarding_date

    UNION ALL
    SELECT 'fee_rate_consistency', 'Validity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Fee-based flag and fee rate disagree'
    FROM ops.account
    WHERE (is_fee_based AND fee_rate_bps <= 0) OR (NOT is_fee_based AND fee_rate_bps <> 0)

    UNION ALL
    SELECT 'closed_client_no_assets', 'Validity', 'error',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR), '0', 'Closed clients hold assets after their closure date'
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_client c ON c.client_key = f.client_key
    WHERE c.closed_date IS NOT NULL AND f.month_end > c.closed_date AND f.total_assets_inr > 0

    UNION ALL
    SELECT 'seeded_client_count', 'Seeded invariant', 'error',
           CASE WHEN COUNT(*) = CAST((SELECT value FROM ops.scenario_config WHERE key = 'expected_clients') AS BIGINT)
                THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR),
           (SELECT value FROM ops.scenario_config WHERE key = 'expected_clients'),
           'Client count must equal the generated scenario manifest'
    FROM ops.client

    UNION ALL
    SELECT 'seeded_advisor_count', 'Seeded invariant', 'error',
           CASE WHEN COUNT(*) = CAST((SELECT value FROM ops.scenario_config WHERE key = 'expected_advisors') AS BIGINT)
                THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR),
           (SELECT value FROM ops.scenario_config WHERE key = 'expected_advisors'),
           'Advisor count must equal the generated scenario manifest'
    FROM ops.advisor

    UNION ALL
    SELECT 'seeded_channel_count', 'Seeded invariant', 'error',
           CASE WHEN COUNT(*) = CAST((SELECT value FROM ops.scenario_config WHERE key = 'expected_channels') AS BIGINT)
                THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR),
           (SELECT value FROM ops.scenario_config WHERE key = 'expected_channels'),
           'Channel count must equal the generated scenario manifest'
    FROM ops.channel

    UNION ALL
    SELECT 'seeded_month_count', 'Seeded invariant', 'error',
           CASE WHEN COUNT(DISTINCT month_end) = CAST((SELECT value FROM ops.scenario_config WHERE key = 'expected_months') AS BIGINT)
                THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(DISTINCT month_end) AS VARCHAR),
           (SELECT value FROM ops.scenario_config WHERE key = 'expected_months'),
           'Observation window must contain the declared number of month-ends'
    FROM ops.monthly_asset_snapshot

    UNION ALL
    SELECT 'seeded_transaction_volume', 'Seeded invariant', 'error',
           CASE WHEN COUNT(*) >= CAST((SELECT value FROM ops.scenario_config WHERE key = 'expected_min_transactions') AS BIGINT)
                THEN 'PASS' ELSE 'FAIL' END,
           CAST(COUNT(*) AS VARCHAR),
           '>= ' || (SELECT value FROM ops.scenario_config WHERE key = 'expected_min_transactions'),
           'Synthetic scenario must contain a meaningful transaction volume'
    FROM ops.transaction

    UNION ALL
    SELECT 'seeded_fee_based_share', 'Seeded invariant', 'error',
           CASE WHEN fee_based_share_pct BETWEEN 15 AND 80 THEN 'PASS' ELSE 'FAIL' END,
           CAST(ROUND(fee_based_share_pct, 2) AS VARCHAR), '15-80',
           'Latest fee-based asset share must be within a plausible synthetic range'
    FROM analytics.kpi_monthly_assets
    WHERE month_start = (SELECT MAX(month_start) FROM analytics.kpi_monthly_assets)

    UNION ALL
    SELECT 'seeded_migration_rate', 'Seeded invariant', 'error',
           CASE WHEN migration_rate_pct BETWEEN 8 AND 55 THEN 'PASS' ELSE 'FAIL' END,
           CAST(migration_rate_pct AS VARCHAR), '8-55',
           'Digital migration-to-advice rate must be within the seeded scenario range'
    FROM analytics.kpi_migration_summary
    WHERE channel_name = 'Digital Direct'

    UNION ALL
    SELECT 'seeded_retention_12m', 'Seeded invariant', 'error',
           CASE WHEN retention_12m_pct BETWEEN 50 AND 100 THEN 'PASS' ELSE 'FAIL' END,
           CAST(retention_12m_pct AS VARCHAR), '50-100',
           '12-month cohort retention must be within a plausible synthetic range'
    FROM analytics.kpi_retention_summary

    UNION ALL
    SELECT 'seeded_advisor_quartile_spread', 'Seeded invariant', 'error',
           CASE WHEN top_q > bottom_q THEN 'PASS' ELSE 'FAIL' END,
           CAST(ROUND(top_q, 2) AS VARCHAR) || ' vs ' || CAST(ROUND(bottom_q, 2) AS VARCHAR), 'top > bottom',
           'Planted productivity spread: top quartile average NNA exceeds bottom quartile'
    FROM (
        SELECT
            AVG(CASE WHEN productivity_quartile = 1 THEN nna_ltm_inr END) AS top_q,
            AVG(CASE WHEN productivity_quartile = 4 THEN nna_ltm_inr END) AS bottom_q
        FROM analytics.kpi_advisor_productivity
    ) q

    UNION ALL
    SELECT 'seeded_channel_asset_order', 'Seeded invariant', 'error',
           CASE WHEN advisory_assets > digital_assets THEN 'PASS' ELSE 'FAIL' END,
           CAST(ROUND(advisory_assets, 2) AS VARCHAR) || ' vs ' || CAST(ROUND(digital_assets, 2) AS VARCHAR),
           'advisory > digital', 'Planted channel mix: Advisory assets exceed Digital assets in the latest month'
    FROM (
        SELECT
            MAX(CASE WHEN channel_name = 'Advisory & Private Client' THEN total_assets_inr END) AS advisory_assets,
            MAX(CASE WHEN channel_name = 'Digital Direct' THEN total_assets_inr END) AS digital_assets
        FROM analytics.kpi_channel_mix
        WHERE month_start = (SELECT MAX(month_start) FROM analytics.kpi_channel_mix)
    ) x
) checks;

CREATE OR REPLACE VIEW analytics.v_data_quality AS
SELECT check_name, category, severity, status, observed, expected, details, checked_at
FROM ops.dq_check_results;

-- Governed warehouse counts for the dashboard (fact + ops + quality).
CREATE OR REPLACE VIEW analytics.v_warehouse_counts AS
SELECT 'clients' AS metric, COUNT(*)::BIGINT AS value FROM ops.client
UNION ALL SELECT 'advisors', COUNT(*)::BIGINT FROM ops.advisor
UNION ALL SELECT 'accounts', COUNT(*)::BIGINT FROM ops.account
UNION ALL SELECT 'transactions', COUNT(*)::BIGINT FROM ops.transaction
UNION ALL SELECT 'monthly snapshots', COUNT(*)::BIGINT FROM ops.monthly_asset_snapshot
UNION ALL SELECT 'engagement events', COUNT(*)::BIGINT FROM ops.engagement_event
UNION ALL SELECT 'SCD2 assignments', COUNT(*)::BIGINT FROM ops.advisor_assignment
UNION ALL SELECT 'fact flows', COUNT(*)::BIGINT FROM analytics.fact_flows
UNION ALL SELECT 'fact monthly assets', COUNT(*)::BIGINT FROM analytics.fact_monthly_assets
UNION ALL SELECT 'fact engagement', COUNT(*)::BIGINT FROM analytics.fact_engagement
UNION ALL SELECT 'KPI checks', COUNT(*)::BIGINT FROM ops.dq_check_results
UNION ALL SELECT 'checks passed', COUNT(*)::BIGINT FROM ops.dq_check_results WHERE status = 'PASS';