-- Client value and top-N views using window functions.
CREATE OR REPLACE VIEW analytics.kpi_client_value AS
WITH latest AS (
    SELECT MAX(month_end) AS max_month FROM analytics.fact_monthly_assets
),
book AS (
    SELECT
        f.client_key,
        c.client_id,
        c.client_name,
        c.segment,
        c.channel_name,
        c.city,
        c.risk_profile,
        a.advisor_name,
        COUNT(DISTINCT f.account_key) AS accounts,
        SUM(f.total_assets_inr) AS total_assets_inr,
        SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee_based_assets_inr
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_client c ON c.client_key = f.client_key
    JOIN latest l ON l.max_month = f.month_end
    LEFT JOIN analytics.v_client_current_advisor a ON a.client_key = f.client_key
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
),
nna AS (
    SELECT
        f.client_key,
        COALESCE(SUM(f.amount_inr), 0) AS nna_ltm_inr
    FROM analytics.fact_flows f
    CROSS JOIN latest l
    WHERE f.is_net_new
      AND f.flow_date > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
      AND f.flow_date <= l.max_month
    GROUP BY 1
),
engagement AS (
    SELECT
        e.client_key,
        COUNT(*) FILTER (WHERE e.event_type = 'plan_created') AS plans_ltm,
        COUNT(*) FILTER (WHERE e.event_type = 'meeting') AS meetings_ltm,
        MAX(CASE WHEN e.event_type = 'plan_created' THEN 1 ELSE 0 END) AS has_plan
    FROM analytics.fact_engagement e
    CROSS JOIN latest l
    WHERE e.event_date > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
      AND e.event_date <= l.max_month
    GROUP BY 1
)
SELECT
    b.*,
    COALESCE(n.nna_ltm_inr, 0) AS nna_ltm_inr,
    COALESCE(e.plans_ltm, 0) AS plans_ltm,
    COALESCE(e.meetings_ltm, 0) AS meetings_ltm,
    COALESCE(e.has_plan, 0) AS has_plan,
    CASE WHEN b.total_assets_inr = 0 THEN NULL
         ELSE 100.0 * b.fee_based_assets_inr / b.total_assets_inr END AS fee_based_share_pct,
    RANK() OVER (ORDER BY b.total_assets_inr DESC) AS asset_rank,
    NTILE(10) OVER (ORDER BY b.total_assets_inr DESC) AS asset_decile,
    ROUND(100.0 * PERCENT_RANK() OVER (ORDER BY b.total_assets_inr), 2) AS asset_percentile,
    ROUND(100.0 * b.total_assets_inr
          / NULLIF(SUM(b.total_assets_inr) OVER (), 0), 2) AS pct_of_book
FROM book b
LEFT JOIN nna n ON n.client_key = b.client_key
LEFT JOIN engagement e ON e.client_key = b.client_key;

CREATE OR REPLACE VIEW analytics.kpi_top_clients AS
SELECT * FROM analytics.kpi_client_value
WHERE asset_rank <= 25;

CREATE OR REPLACE VIEW analytics.kpi_client_segments AS
WITH latest AS (
    SELECT MAX(month_end) AS max_month FROM analytics.fact_monthly_assets
),
assets AS (
    SELECT
        c.segment,
        COUNT(DISTINCT f.client_key) AS clients,
        COUNT(DISTINCT f.account_key) AS accounts,
        SUM(f.total_assets_inr) AS total_assets_inr,
        SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee_based_assets_inr
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_client c ON c.client_key = f.client_key
    JOIN latest l ON l.max_month = f.month_end
    GROUP BY 1
),
nna AS (
    SELECT
        c.segment,
        COALESCE(SUM(f.amount_inr), 0) AS nna_ltm_inr
    FROM analytics.fact_flows f
    JOIN analytics.dim_client c ON c.client_key = f.client_key
    CROSS JOIN latest l
    WHERE f.is_net_new
      AND f.flow_date > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
      AND f.flow_date <= l.max_month
    GROUP BY 1
)
SELECT
    a.segment,
    a.clients,
    a.accounts,
    a.total_assets_inr,
    a.fee_based_assets_inr,
    ROUND(100.0 * a.fee_based_assets_inr / NULLIF(a.total_assets_inr, 0), 2) AS fee_based_share_pct,
    ROUND(100.0 * a.total_assets_inr
          / NULLIF(SUM(a.total_assets_inr) OVER (), 0), 2) AS assets_share_pct,
    ROUND(a.total_assets_inr / NULLIF(a.clients, 0), 2) AS avg_assets_per_client_inr,
    COALESCE(n.nna_ltm_inr, 0) AS nna_ltm_inr
FROM assets a
LEFT JOIN nna n ON n.segment = a.segment;
