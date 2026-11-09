-- Monthly net new assets (NNA).
--
-- Definition: NNA = external client inflows (deposits + transfers in) minus
-- external client outflows (withdrawals + transfers out), in INR, by calendar
-- month.  Dividends, interest, fees and security trades are internal to the
-- client relationship and are excluded.  This is a gross-flow measure, not
-- investment performance.
CREATE OR REPLACE VIEW analytics.kpi_monthly_flows AS
WITH base AS (
    SELECT
        d.month_start,
        SUM(CASE WHEN f.is_net_new AND f.amount_inr > 0 THEN f.amount_inr ELSE 0 END) AS inflows_inr,
        SUM(CASE WHEN f.is_net_new AND f.amount_inr < 0 THEN -f.amount_inr ELSE 0 END) AS outflows_inr,
        SUM(CASE WHEN f.is_net_new THEN f.amount_inr ELSE 0 END) AS net_new_assets_inr,
        COUNT(*) FILTER (WHERE f.is_net_new) AS net_new_flow_count,
        COUNT(DISTINCT f.client_key) FILTER (WHERE f.is_net_new) AS net_new_client_count
    FROM analytics.fact_flows f
    JOIN analytics.dim_date d ON d.date_key = f.date_key
    GROUP BY 1
)
SELECT
    month_start,
    EXTRACT(year FROM month_start)::INTEGER AS calendar_year,
    inflows_inr,
    outflows_inr,
    net_new_assets_inr,
    inflows_inr - outflows_inr AS nna_check_inr,
    net_new_flow_count,
    net_new_client_count,
    LAG(net_new_assets_inr) OVER (ORDER BY month_start) AS prior_month_nna_inr,
    net_new_assets_inr - LAG(net_new_assets_inr) OVER (ORDER BY month_start) AS nna_mom_change_inr,
    CASE
        WHEN LAG(net_new_assets_inr) OVER (ORDER BY month_start) IS NULL
          OR LAG(net_new_assets_inr) OVER (ORDER BY month_start) = 0 THEN NULL
        ELSE 100.0 * (net_new_assets_inr - LAG(net_new_assets_inr) OVER (ORDER BY month_start))
             / LAG(net_new_assets_inr) OVER (ORDER BY month_start)
    END AS nna_mom_pct,
    SUM(net_new_assets_inr) OVER (
        ORDER BY month_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_nna_inr,
    SUM(net_new_assets_inr) OVER (
        PARTITION BY EXTRACT(year FROM month_start)
        ORDER BY month_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS nna_ytd_inr,
    SUM(net_new_assets_inr) OVER (
        ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS nna_ltm_inr
FROM base;

-- Flow-type detail for the funnel / drill-down table.
CREATE OR REPLACE VIEW analytics.kpi_flow_types AS
SELECT
    d.month_start,
    f.flow_type,
    f.direction,
    COUNT(*) AS flow_count,
    COUNT(DISTINCT f.client_key) AS client_count,
    SUM(f.amount_inr) AS gross_amount_inr,
    SUM(CASE WHEN f.is_net_new THEN f.amount_inr ELSE 0 END) AS nna_inr
FROM analytics.fact_flows f
JOIN analytics.dim_date d ON d.date_key = f.date_key
GROUP BY 1, 2, 3;
