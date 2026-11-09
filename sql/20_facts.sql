-- Transaction-grain flow fact.  amount_inr is signed: inflows positive,
-- outflows negative, internal movements (fees, dividends, trades) are not
-- net new assets.  advisor_key is resolved with an as-of SCD2 join.
CREATE OR REPLACE TABLE analytics.fact_flows AS
SELECT
    ROW_NUMBER() OVER (ORDER BY t.transaction_date, t.transaction_id) AS flow_key,
    t.transaction_id,
    d.date_key,
    d.date AS flow_date,
    d.month_start,
    c.client_key,
    ac.account_key,
    COALESCE(aa.advisor_key, 0) AS advisor_key,
    c.channel_key,
    t.transaction_type AS flow_type,
    t.direction,
    t.is_net_new,
    t.is_fee_based,
    t.amount_inr
FROM ops.transaction t
JOIN analytics.dim_date d ON d.date = t.transaction_date
JOIN analytics.dim_account ac ON ac.account_id = t.account_id
JOIN analytics.dim_client c ON c.client_key = ac.client_key
LEFT JOIN analytics.dim_advisor_assignment aa
  ON aa.client_key = c.client_key
 AND t.transaction_date BETWEEN aa.effective_from
     AND COALESCE(aa.effective_to, DATE '9999-12-31');

-- Account-month asset fact.  The recurrence is:
--   total_assets = beginning + market_growth + net_new + internal_income - fee
-- estimated_fee_revenue_inr is the synthetic fee debited in the month.
CREATE OR REPLACE TABLE analytics.fact_monthly_assets AS
SELECT
    ROW_NUMBER() OVER (ORDER BY s.month_end, s.account_id) AS monthly_asset_key,
    s.snapshot_id,
    d.date_key AS month_date_key,
    s.month_end,
    d.month_start,
    c.client_key,
    ac.account_key,
    COALESCE(aa.advisor_key, 0) AS advisor_key,
    c.channel_key,
    s.beginning_assets_inr,
    s.market_growth_inr,
    s.net_new_assets_inr,
    s.internal_income_inr,
    s.fee_amount_inr,
    s.market_return_pct,
    s.market_value_inr,
    s.cash_balance_inr,
    s.total_assets_inr,
    s.fee_amount_inr AS estimated_fee_revenue_inr,
    ac.fee_rate_bps,
    ac.is_fee_based
FROM ops.monthly_asset_snapshot s
JOIN analytics.dim_date d ON d.date = s.month_end
JOIN analytics.dim_account ac ON ac.account_id = s.account_id
JOIN analytics.dim_client c ON c.client_key = ac.client_key
LEFT JOIN analytics.dim_advisor_assignment aa
  ON aa.client_key = c.client_key
 AND s.month_end BETWEEN aa.effective_from
     AND COALESCE(aa.effective_to, DATE '9999-12-31');

-- Engagement fact.  Planning events are the synthetic advice milestone used
-- by the migration metric; they are assumptions, not causal estimates.
CREATE OR REPLACE TABLE analytics.fact_engagement AS
SELECT
    ROW_NUMBER() OVER (ORDER BY e.event_date, e.event_id) AS engagement_key,
    e.event_id,
    d.date_key,
    e.event_date,
    d.month_start,
    c.client_key,
    COALESCE(aa.advisor_key, 0) AS advisor_key,
    c.channel_key,
    e.event_type,
    e.duration_minutes,
    e.is_planning_event
FROM ops.engagement_event e
JOIN analytics.dim_date d ON d.date = e.event_date
JOIN analytics.dim_client c ON c.client_id = e.client_id
LEFT JOIN analytics.dim_advisor_assignment aa
  ON aa.client_key = c.client_key
 AND e.event_date BETWEEN aa.effective_from
     AND COALESCE(aa.effective_to, DATE '9999-12-31');
