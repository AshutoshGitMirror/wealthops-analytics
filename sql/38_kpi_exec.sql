-- One-row executive snapshot as of the latest month.
CREATE OR REPLACE VIEW analytics.kpi_exec_overview AS
WITH latest_assets AS (
    SELECT * FROM analytics.kpi_monthly_assets
    WHERE month_start = (SELECT MAX(month_start) FROM analytics.kpi_monthly_assets)
),
latest_flows AS (
    SELECT * FROM analytics.kpi_monthly_flows
    WHERE month_start = (SELECT MAX(month_start) FROM analytics.kpi_monthly_flows)
)
SELECT
    la.month_start AS as_of_month,
    CAST(la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY AS DATE) AS as_of_month_end,
    la.total_assets_inr,
    la.fee_based_assets_inr,
    la.fee_based_share_pct,
    la.clients_with_assets AS active_clients,
    la.accounts_with_assets AS active_accounts,
    la.avg_assets_per_client_inr,
    la.net_new_assets_inr AS latest_month_nna_inr,
    lf.nna_ltm_inr,
    lf.nna_ytd_inr,
    (SELECT COUNT(*) FROM analytics.dim_advisor WHERE advisor_key > 0) AS advisors,
    (SELECT migration_rate_pct FROM analytics.kpi_migration_summary) AS migration_rate_pct,
    (SELECT retention_12m_pct FROM analytics.kpi_retention_summary) AS retention_12m_pct,
    (SELECT COUNT(*) FROM analytics.fact_engagement e
      WHERE e.event_type = 'plan_created'
        AND e.event_date > CAST((la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) - INTERVAL 12 MONTH AS DATE)
        AND e.event_date <= la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) AS plans_created_ltm,
    (SELECT COALESCE(SUM(f.estimated_fee_revenue_inr), 0) FROM analytics.fact_monthly_assets f
      WHERE f.month_end > CAST((la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) - INTERVAL 12 MONTH AS DATE)
        AND f.month_end <= la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) AS estimated_fee_revenue_ltm,
    (SELECT COUNT(*) FROM analytics.fact_engagement e
      WHERE e.event_type = 'meeting'
        AND e.event_date > CAST((la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) - INTERVAL 12 MONTH AS DATE)
        AND e.event_date <= la.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY) AS advice_meetings_ltm
FROM latest_assets la
CROSS JOIN latest_flows lf;
