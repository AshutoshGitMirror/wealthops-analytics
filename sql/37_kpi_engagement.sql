-- Engagement and planning activity.  These are synthetic activity records;
-- they do not measure advice quality or client outcomes.
CREATE OR REPLACE VIEW analytics.kpi_engagement_monthly AS
SELECT
    d.month_start,
    e.event_type,
    COUNT(*) AS events,
    COUNT(DISTINCT e.client_key) AS clients,
    ROUND(AVG(e.duration_minutes), 1) AS avg_duration_minutes,
    SUM(e.duration_minutes) AS total_minutes,
    COUNT(*) FILTER (WHERE e.is_planning_event) AS planning_events
FROM analytics.fact_engagement e
JOIN analytics.dim_date d ON d.date_key = e.date_key
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics.kpi_engagement_summary AS
SELECT
    d.month_start,
    COUNT(*) AS events,
    COUNT(DISTINCT e.client_key) AS engaged_clients,
    COUNT(*) FILTER (WHERE e.event_type = 'meeting') AS advice_meetings,
    COUNT(*) FILTER (WHERE e.event_type = 'plan_created') AS plans_created,
    COUNT(*) FILTER (WHERE e.event_type = 'plan_review') AS plan_reviews,
    SUM(e.duration_minutes) AS total_minutes
FROM analytics.fact_engagement e
JOIN analytics.dim_date d ON d.date_key = e.date_key
GROUP BY 1;
