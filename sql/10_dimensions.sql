-- Conformed dimensions for the star schema.
-- Units: all monetary columns are Indian rupees (INR), nominal.

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE TABLE analytics.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE)                      AS date,
    CAST(EXTRACT(year FROM d) AS INTEGER) AS year,
    CAST(EXTRACT(quarter FROM d) AS INTEGER) AS quarter,
    CAST(EXTRACT(month FROM d) AS INTEGER) AS month,
    strftime(d, '%b')                    AS month_name,
    CAST(date_trunc('month', d) AS DATE) AS month_start,
    CAST(last_day(d) AS DATE)            AS month_end,
    CAST(strftime(d, '%Y-%m') AS VARCHAR) AS year_month,
    CASE WHEN CAST(d AS DATE) = CAST(last_day(d) AS DATE) THEN TRUE ELSE FALSE END AS is_month_end
FROM generate_series(DATE '2023-01-01', DATE '2026-12-31', INTERVAL 1 DAY) AS t(d);

CREATE OR REPLACE TABLE analytics.dim_channel AS
SELECT
    channel_id   AS channel_key,
    channel_id,
    channel_code,
    channel_name,
    channel_type
FROM ops.channel;

CREATE OR REPLACE TABLE analytics.dim_advisor AS
WITH base AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY advisor_id) AS advisor_key,
        advisor_id,
        advisor_name,
        region,
        segment_specialty,
        hire_date,
        status
    FROM ops.advisor
)
SELECT
    0 AS advisor_key,
    'ADV00' AS advisor_id,
    'Unassigned' AS advisor_name,
    'Unassigned' AS region,
    'Unassigned' AS segment_specialty,
    DATE '1900-01-01' AS hire_date,
    'N/A' AS status
UNION ALL
SELECT * FROM base;

CREATE OR REPLACE TABLE analytics.dim_client AS
SELECT
    ROW_NUMBER() OVER (ORDER BY c.client_id) AS client_key,
    c.client_id,
    c.client_name,
    c.channel_id AS channel_key,
    ch.channel_code,
    ch.channel_name,
    c.segment,
    c.risk_profile,
    c.city,
    c.onboarding_date,
    CAST(date_trunc('month', c.onboarding_date) AS DATE) AS cohort_month,
    c.status,
    c.closed_date,
    CASE WHEN c.status = 'Closed' THEN FALSE ELSE TRUE END AS is_active,
    date_diff('month', c.onboarding_date, DATE '2026-10-31') AS tenure_months
FROM ops.client c
JOIN ops.channel ch ON ch.channel_id = c.channel_id;

CREATE OR REPLACE TABLE analytics.dim_account AS
SELECT
    ROW_NUMBER() OVER (ORDER BY a.account_id) AS account_key,
    a.account_id,
    c.client_key,
    a.account_type,
    a.opened_date,
    a.status,
    a.fee_rate_bps,
    a.is_fee_based,
    date_diff('day', a.opened_date, DATE '2026-10-31') AS account_age_days
FROM ops.account a
JOIN analytics.dim_client c ON c.client_id = a.client_id;

CREATE OR REPLACE TABLE analytics.dim_advisor_assignment AS
SELECT
    ROW_NUMBER() OVER (ORDER BY aa.client_id, aa.effective_from) AS assignment_key,
    c.client_key,
    ad.advisor_key,
    aa.assignment_id,
    aa.effective_from,
    aa.effective_to,
    aa.is_current,
    aa.assignment_reason,
    date_diff('day', aa.effective_from, COALESCE(aa.effective_to, DATE '2026-10-31')) AS duration_days
FROM ops.advisor_assignment aa
JOIN analytics.dim_client c ON c.client_id = aa.client_id
JOIN analytics.dim_advisor ad ON ad.advisor_id = aa.advisor_id;

-- Handy current-assignment view used by the dashboard and client explorer.
CREATE OR REPLACE VIEW analytics.v_client_current_advisor AS
SELECT
    c.client_key,
    c.client_id,
    c.client_name,
    c.segment,
    c.channel_name,
    a.advisor_key,
    a.advisor_name,
    a.region,
    aa.effective_from,
    aa.assignment_reason
FROM analytics.dim_client c
JOIN analytics.dim_advisor_assignment aa
  ON aa.client_key = c.client_key AND aa.is_current
JOIN analytics.dim_advisor a ON a.advisor_key = aa.advisor_key;
