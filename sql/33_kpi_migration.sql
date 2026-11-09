-- Migration to advice (synthetic scenario definition).
--
-- Eligible population: clients acquired through the Digital Direct channel who
-- were onboarded at least 90 days before the observation end.  Migrated: an
-- eligible client with at least one completed plan_created engagement event.
-- This is a proxy milestone for the scenario, not a causal estimate or a
-- production "advice conversion" definition.
CREATE OR REPLACE VIEW analytics.kpi_migration_to_advice AS
WITH eligible AS (
    SELECT
        c.client_key,
        c.channel_key,
        c.channel_name,
        c.cohort_month,
        c.onboarding_date,
        MAX(CASE WHEN e.event_type = 'plan_created' THEN 1 ELSE 0 END) AS has_plan,
        MIN(CASE WHEN e.event_type = 'plan_created' THEN e.event_date END) AS first_plan_date
    FROM analytics.dim_client c
    LEFT JOIN analytics.fact_engagement e ON e.client_key = c.client_key
    WHERE c.channel_code = 'DIGITAL'
      AND c.onboarding_date <= CAST(
          (SELECT MAX(month_end) FROM analytics.fact_monthly_assets) - INTERVAL 90 DAY
          AS DATE
      )
    GROUP BY 1, 2, 3, 4, 5
)
SELECT
    cohort_month,
    channel_name,
    COUNT(*) AS eligible_clients,
    SUM(has_plan)::INTEGER AS migrated_clients,
    COUNT(*) - SUM(has_plan)::INTEGER AS not_migrated_clients,
    ROUND(100.0 * SUM(has_plan) / NULLIF(COUNT(*), 0), 2) AS migration_rate_pct,
    MIN(first_plan_date) AS first_plan_date
FROM eligible
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics.kpi_migration_summary AS
SELECT
    channel_name,
    SUM(eligible_clients) AS eligible_clients,
    SUM(migrated_clients) AS migrated_clients,
    ROUND(100.0 * SUM(migrated_clients) / NULLIF(SUM(eligible_clients), 0), 2) AS migration_rate_pct,
    MAX(cohort_month) AS latest_cohort_month
FROM analytics.kpi_migration_to_advice
GROUP BY 1;

-- Funnel by channel.  "Engaged" means any recorded engagement event;
-- "planned" means a completed plan_created event; "fee-based" means the client
-- had a positive fee-based balance in the latest month.
CREATE OR REPLACE VIEW analytics.kpi_advice_funnel AS
WITH latest AS (
    SELECT MAX(month_end) AS max_month FROM analytics.fact_monthly_assets
),
engagement AS (
    SELECT
        e.channel_key,
        COUNT(DISTINCT e.client_key) AS engaged_clients,
        COUNT(DISTINCT CASE WHEN e.event_type = 'plan_created' THEN e.client_key END) AS planned_clients
    FROM analytics.fact_engagement e
    GROUP BY 1
),
fee_based AS (
    SELECT
        f.channel_key,
        COUNT(DISTINCT CASE WHEN f.is_fee_based AND f.total_assets_inr > 0 THEN f.client_key END) AS fee_based_clients
    FROM analytics.fact_monthly_assets f
    JOIN latest l ON l.max_month = f.month_end
    GROUP BY 1
),
clients AS (
    SELECT channel_key, channel_name, COUNT(*) AS clients
    FROM analytics.dim_client
    GROUP BY 1, 2
)
SELECT
    c.channel_key,
    c.channel_name,
    c.clients,
    COALESCE(e.engaged_clients, 0) AS engaged_clients,
    COALESCE(e.planned_clients, 0) AS planned_clients,
    COALESCE(fb.fee_based_clients, 0) AS fee_based_clients,
    ROUND(100.0 * COALESCE(e.engaged_clients, 0) / NULLIF(c.clients, 0), 2) AS engagement_rate_pct,
    ROUND(100.0 * COALESCE(e.planned_clients, 0) / NULLIF(c.clients, 0), 2) AS planning_rate_pct,
    ROUND(100.0 * COALESCE(fb.fee_based_clients, 0) / NULLIF(c.clients, 0), 2) AS fee_based_rate_pct
FROM clients c
LEFT JOIN engagement e ON e.channel_key = c.channel_key
LEFT JOIN fee_based fb ON fb.channel_key = c.channel_key;
