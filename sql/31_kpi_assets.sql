-- Monthly asset and fee-based asset KPIs.
-- Fee-based assets are accounts whose account_type is managed/advisory and
-- is_fee_based is true.  Share is fee-based assets / total assets * 100.
CREATE OR REPLACE VIEW analytics.kpi_monthly_assets AS
WITH base AS (
    SELECT
        d.month_start,
        SUM(f.total_assets_inr) AS total_assets_inr,
        SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee_based_assets_inr,
        SUM(f.estimated_fee_revenue_inr) AS estimated_fee_revenue_inr,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.client_key END) AS clients_with_assets,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.account_key END) AS accounts_with_assets
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_date d ON d.date_key = f.month_date_key
    GROUP BY 1
)
SELECT
    b.month_start,
    EXTRACT(year FROM b.month_start)::INTEGER AS calendar_year,
    b.total_assets_inr,
    b.fee_based_assets_inr,
    b.total_assets_inr - b.fee_based_assets_inr AS non_fee_based_assets_inr,
    CASE WHEN b.total_assets_inr = 0 THEN NULL
         ELSE 100.0 * b.fee_based_assets_inr / b.total_assets_inr END AS fee_based_share_pct,
    b.estimated_fee_revenue_inr,
    b.clients_with_assets,
    b.accounts_with_assets,
    CASE WHEN b.clients_with_assets = 0 THEN NULL
         ELSE b.total_assets_inr / b.clients_with_assets END AS avg_assets_per_client_inr,
    LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) AS prior_month_assets_inr,
    CASE WHEN LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) IS NULL
              OR LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) = 0 THEN NULL
         ELSE 100.0 * (b.total_assets_inr - LAG(b.total_assets_inr) OVER (ORDER BY b.month_start))
              / LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) END AS assets_mom_pct,
    CASE WHEN LAG(b.fee_based_assets_inr) OVER (ORDER BY b.month_start) IS NULL
              OR LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) = 0 THEN NULL
         ELSE 100.0 * b.fee_based_assets_inr / b.total_assets_inr
              - 100.0 * LAG(b.fee_based_assets_inr) OVER (ORDER BY b.month_start)
                / LAG(b.total_assets_inr) OVER (ORDER BY b.month_start) END AS fee_based_share_mom_pp,
    AVG(CASE WHEN b.total_assets_inr = 0 THEN NULL
             ELSE 100.0 * b.fee_based_assets_inr / b.total_assets_inr END) OVER (
        ORDER BY b.month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS fee_based_share_3m_avg_pct,
    COALESCE(mf.inflows_inr, 0) AS inflows_inr,
    COALESCE(mf.outflows_inr, 0) AS outflows_inr,
    COALESCE(mf.net_new_assets_inr, 0) AS net_new_assets_inr,
    COALESCE(mf.nna_ltm_inr, 0) AS nna_ltm_inr
FROM base b
LEFT JOIN analytics.kpi_monthly_flows mf ON mf.month_start = b.month_start;
