-- Advisor book productivity as of the latest month, plus a monthly trend view.
-- Quartile 1 = highest trailing-12-month NNA (top quartile); rank 1 = highest.
CREATE OR REPLACE VIEW analytics.kpi_advisor_productivity AS
WITH latest AS (
    SELECT MAX(month_end) AS max_month FROM analytics.fact_monthly_assets
),
book AS (
    SELECT
        a.advisor_key,
        a.advisor_id,
        a.advisor_name,
        a.region,
        a.segment_specialty,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.client_key END) AS clients,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.account_key END) AS accounts,
        COALESCE(SUM(f.total_assets_inr), 0) AS total_assets_inr,
        COALESCE(SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END), 0) AS fee_based_assets_inr
    FROM analytics.dim_advisor a
    LEFT JOIN analytics.fact_monthly_assets f
      ON f.advisor_key = a.advisor_key
     AND f.month_end = (SELECT max_month FROM latest)
    WHERE a.advisor_key > 0
    GROUP BY 1, 2, 3, 4, 5
),
nna AS (
    SELECT
        f.advisor_key,
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
        e.advisor_key,
        COUNT(*) FILTER (WHERE e.event_type = 'plan_created') AS plans_ltm,
        COUNT(*) FILTER (WHERE e.event_type = 'meeting') AS meetings_ltm,
        COALESCE(SUM(e.duration_minutes), 0) AS engagement_minutes_ltm
    FROM analytics.fact_engagement e
    CROSS JOIN latest l
    WHERE e.event_date > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
      AND e.event_date <= l.max_month
    GROUP BY 1
),
fees AS (
    SELECT
        f.advisor_key,
        COALESCE(SUM(f.estimated_fee_revenue_inr), 0) AS estimated_fee_revenue_ltm
    FROM analytics.fact_monthly_assets f
    CROSS JOIN latest l
    WHERE f.month_end > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
      AND f.month_end <= l.max_month
    GROUP BY 1
),
metrics AS (
    SELECT
        b.advisor_key,
        b.advisor_id,
        b.advisor_name,
        b.region,
        b.segment_specialty,
        b.clients,
        b.accounts,
        b.total_assets_inr,
        b.fee_based_assets_inr,
        CASE WHEN b.total_assets_inr = 0 THEN NULL
             ELSE 100.0 * b.fee_based_assets_inr / b.total_assets_inr END AS fee_based_share_pct,
        b.total_assets_inr - b.fee_based_assets_inr AS non_fee_based_assets_inr,
        COALESCE(n.nna_ltm_inr, 0) AS nna_ltm_inr,
        COALESCE(e.plans_ltm, 0) AS plans_ltm,
        COALESCE(e.meetings_ltm, 0) AS meetings_ltm,
        COALESCE(e.engagement_minutes_ltm, 0) AS engagement_minutes_ltm,
        COALESCE(fe.estimated_fee_revenue_ltm, 0) AS estimated_fee_revenue_ltm,
        CASE WHEN b.clients = 0 THEN NULL ELSE b.total_assets_inr / b.clients END AS assets_per_client_inr,
        CASE WHEN b.clients = 0 THEN NULL ELSE COALESCE(n.nna_ltm_inr, 0) / b.clients END AS nna_per_client_inr,
        CASE WHEN b.clients = 0 THEN NULL ELSE COALESCE(e.meetings_ltm, 0)::DOUBLE / b.clients END AS meetings_per_client
    FROM book b
    LEFT JOIN nna n ON n.advisor_key = b.advisor_key
    LEFT JOIN engagement e ON e.advisor_key = b.advisor_key
    LEFT JOIN fees fe ON fe.advisor_key = b.advisor_key
)
SELECT
    m.*,
    ROUND(100.0 * m.total_assets_inr
          / NULLIF(SUM(m.total_assets_inr) OVER (), 0), 2) AS pct_of_book,
    RANK() OVER (ORDER BY m.nna_ltm_inr DESC) AS nna_rank,
    NTILE(4) OVER (ORDER BY m.nna_ltm_inr DESC) AS productivity_quartile,
    m.nna_ltm_inr - LAG(m.nna_ltm_inr) OVER (ORDER BY m.nna_ltm_inr DESC) AS nna_gap_to_next_inr
FROM metrics m;

CREATE OR REPLACE VIEW analytics.kpi_advisor_monthly AS
WITH assets AS (
    SELECT
        d.month_start,
        f.advisor_key,
        SUM(f.total_assets_inr) AS total_assets_inr,
        SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee_based_assets_inr,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.client_key END) AS clients
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_date d ON d.date_key = f.month_date_key
    GROUP BY 1, 2
),
nna AS (
    SELECT
        d.month_start,
        f.advisor_key,
        SUM(f.amount_inr) AS nna_inr
    FROM analytics.fact_flows f
    JOIN analytics.dim_date d ON d.date_key = f.date_key
    WHERE f.is_net_new
    GROUP BY 1, 2
)
SELECT
    a.month_start,
    a.advisor_key,
    ad.advisor_name,
    ad.region,
    ad.segment_specialty,
    a.clients,
    a.total_assets_inr,
    a.fee_based_assets_inr,
    COALESCE(n.nna_inr, 0) AS nna_inr,
    LAG(a.total_assets_inr) OVER (PARTITION BY a.advisor_key ORDER BY a.month_start) AS prior_month_assets_inr,
    SUM(COALESCE(n.nna_inr, 0)) OVER (
        PARTITION BY a.advisor_key ORDER BY a.month_start
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_nna_inr,
    RANK() OVER (PARTITION BY a.month_start ORDER BY a.total_assets_inr DESC) AS assets_rank
FROM assets a
JOIN analytics.dim_advisor ad ON ad.advisor_key = a.advisor_key
LEFT JOIN nna n ON n.month_start = a.month_start AND n.advisor_key = a.advisor_key;

CREATE OR REPLACE VIEW analytics.kpi_top_advisors AS
SELECT * FROM analytics.kpi_advisor_productivity
WHERE nna_rank <= 10;
