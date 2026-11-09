-- Client and asset mix by acquisition/servicing channel.
-- Channel is the client's acquisition channel in this synthetic dataset; it is
-- not a product-holding or advice-channel measure.
CREATE OR REPLACE VIEW analytics.kpi_channel_mix AS
WITH assets AS (
    SELECT
        d.month_start,
        ch.channel_key,
        ch.channel_code,
        ch.channel_name,
        ch.channel_type,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.client_key END) AS clients,
        COUNT(DISTINCT CASE WHEN f.total_assets_inr > 0 THEN f.account_key END) AS accounts,
        SUM(f.total_assets_inr) AS total_assets_inr,
        SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee_based_assets_inr
    FROM analytics.fact_monthly_assets f
    JOIN analytics.dim_date d ON d.date_key = f.month_date_key
    JOIN analytics.dim_channel ch ON ch.channel_key = f.channel_key
    GROUP BY 1, 2, 3, 4, 5
),
nna AS (
    SELECT
        d.month_start,
        f.channel_key,
        SUM(f.amount_inr) AS nna_inr
    FROM analytics.fact_flows f
    JOIN analytics.dim_date d ON d.date_key = f.date_key
    WHERE f.is_net_new
    GROUP BY 1, 2
)
SELECT
    a.month_start,
    a.channel_key,
    a.channel_code,
    a.channel_name,
    a.channel_type,
    a.clients,
    a.accounts,
    a.total_assets_inr,
    a.fee_based_assets_inr,
    CASE WHEN a.total_assets_inr = 0 THEN NULL
         ELSE 100.0 * a.fee_based_assets_inr / a.total_assets_inr END AS fee_based_share_pct,
    ROUND(100.0 * a.total_assets_inr
          / NULLIF(SUM(a.total_assets_inr) OVER (PARTITION BY a.month_start), 0), 2) AS assets_share_pct,
    ROUND(100.0 * a.clients
          / NULLIF(SUM(a.clients) OVER (PARTITION BY a.month_start), 0), 2) AS clients_share_pct,
    COALESCE(n.nna_inr, 0) AS nna_inr,
    SUM(COALESCE(n.nna_inr, 0)) OVER (
        PARTITION BY a.channel_key ORDER BY a.month_start
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS nna_ltm_inr
FROM assets a
LEFT JOIN nna n ON n.month_start = a.month_start AND n.channel_key = a.channel_key;
