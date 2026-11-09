-- Load the generated parquet files into the operational schema.
-- __RAW_DIR__ is substituted by the Python pipeline with an absolute path.

DELETE FROM ops.engagement_event;
DELETE FROM ops.monthly_asset_snapshot;
DELETE FROM ops.transaction;
DELETE FROM ops.advisor_assignment;
DELETE FROM ops.account;
DELETE FROM ops.client;
DELETE FROM ops.advisor;
DELETE FROM ops.channel;

INSERT INTO ops.channel BY NAME
SELECT * FROM read_parquet('__RAW_DIR__/channel.parquet');

INSERT INTO ops.advisor
SELECT
    advisor_id,
    advisor_name,
    region,
    segment_specialty,
    CAST(hire_date AS DATE),
    status
FROM read_parquet('__RAW_DIR__/advisor.parquet');

INSERT INTO ops.client
SELECT
    client_id,
    client_name,
    channel_id,
    segment,
    risk_profile,
    city,
    CAST(onboarding_date AS DATE),
    status,
    CAST(closed_date AS DATE)
FROM read_parquet('__RAW_DIR__/client.parquet');

INSERT INTO ops.account
SELECT
    account_id,
    client_id,
    account_type,
    CAST(opened_date AS DATE),
    status,
    fee_rate_bps,
    is_fee_based
FROM read_parquet('__RAW_DIR__/account.parquet');

INSERT INTO ops.advisor_assignment
SELECT
    assignment_id,
    client_id,
    advisor_id,
    CAST(effective_from AS DATE),
    CAST(effective_to AS DATE),
    assignment_reason,
    is_current
FROM read_parquet('__RAW_DIR__/advisor_assignment.parquet');

INSERT INTO ops.transaction
SELECT
    transaction_id,
    account_id,
    client_id,
    channel_id,
    CAST(transaction_date AS DATE),
    transaction_type,
    direction,
    amount_inr,
    is_net_new,
    is_fee_based
FROM read_parquet('__RAW_DIR__/transaction.parquet');

INSERT INTO ops.monthly_asset_snapshot
SELECT
    snapshot_id,
    account_id,
    client_id,
    CAST(month_end AS DATE),
    beginning_assets_inr,
    market_growth_inr,
    net_new_assets_inr,
    internal_income_inr,
    fee_amount_inr,
    market_return_pct,
    market_value_inr,
    cash_balance_inr,
    total_assets_inr
FROM read_parquet('__RAW_DIR__/monthly_asset_snapshot.parquet');

INSERT INTO ops.engagement_event
SELECT
    event_id,
    client_id,
    advisor_id,
    channel_id,
    CAST(event_date AS DATE),
    event_type,
    duration_minutes,
    is_planning_event
FROM read_parquet('__RAW_DIR__/engagement_event.parquet');
