-- Client cohort asset retention.
--
-- Cohort = month of onboarding.  Retained at month N = the client has a
-- positive total asset balance in that month.  This measures asset presence,
-- not product-level retention or revenue retention.  Cohorts without enough
-- elapsed history simply have fewer observed months.
CREATE OR REPLACE VIEW analytics.kpi_cohort_retention AS
WITH cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM analytics.dim_client
    GROUP BY 1
),
activity AS (
    SELECT
        c.cohort_month,
        date_diff('month', c.cohort_month, d.month_start)::INTEGER AS months_since_onboarding,
        COUNT(DISTINCT f.client_key) AS retained_clients
    FROM analytics.dim_client c
    JOIN analytics.fact_monthly_assets f ON f.client_key = c.client_key
    JOIN analytics.dim_date d ON d.date_key = f.month_date_key
    WHERE f.total_assets_inr > 0
      AND date_diff('month', c.cohort_month, d.month_start) BETWEEN 0 AND
          (SELECT date_diff('month', MIN(month_start), MAX(month_start))
           FROM analytics.fact_monthly_assets)
    GROUP BY 1, 2
)
SELECT
    cs.cohort_month,
    o.months_since_onboarding,
    cs.cohort_size,
    CASE
        WHEN (cs.cohort_month + o.months_since_onboarding * INTERVAL 1 MONTH)::DATE
             BETWEEN (SELECT MIN(month_start) FROM analytics.fact_monthly_assets)
             AND (SELECT MAX(month_start) FROM analytics.fact_monthly_assets)
        THEN COALESCE(a.retained_clients, 0)
        ELSE NULL
    END AS retained_clients,
    CASE
        WHEN (cs.cohort_month + o.months_since_onboarding * INTERVAL 1 MONTH)::DATE
             BETWEEN (SELECT MIN(month_start) FROM analytics.fact_monthly_assets)
             AND (SELECT MAX(month_start) FROM analytics.fact_monthly_assets)
        THEN ROUND(100.0 * COALESCE(a.retained_clients, 0) / NULLIF(cs.cohort_size, 0), 2)
        ELSE NULL
    END AS retention_rate_pct,
    CASE
        WHEN (cs.cohort_month + o.months_since_onboarding * INTERVAL 1 MONTH)::DATE
             BETWEEN (SELECT MIN(month_start) FROM analytics.fact_monthly_assets)
             AND (SELECT MAX(month_start) FROM analytics.fact_monthly_assets)
        THEN TRUE ELSE FALSE
    END AS is_observed
FROM cohort_sizes cs
CROSS JOIN generate_series(
    0,
    (SELECT date_diff('month', MIN(month_start), MAX(month_start))
     FROM analytics.fact_monthly_assets)
) AS o(months_since_onboarding)
LEFT JOIN activity a
  ON a.cohort_month = cs.cohort_month
 AND a.months_since_onboarding = o.months_since_onboarding;

CREATE OR REPLACE VIEW analytics.kpi_retention_summary AS
SELECT
    12 AS months_since_onboarding,
    SUM(cohort_size) AS eligible_cohort_clients,
    SUM(retained_clients) AS retained_clients,
    ROUND(100.0 * SUM(retained_clients) / NULLIF(SUM(cohort_size), 0), 2) AS retention_12m_pct
FROM analytics.kpi_cohort_retention
WHERE months_since_onboarding = 12
  AND is_observed;
