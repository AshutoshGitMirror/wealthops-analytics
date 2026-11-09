"""Mathematical checks for the governed KPI views.

These tests re-derive headline metrics from the facts and dimensions rather
than trusting the view definitions.  They are intentionally independent of the
synthetic generator's planted relationships.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TOL = 1e-6


def close(actual, expected, tol: float = 1e-6) -> bool:
    return np.allclose(
        np.asarray(actual, dtype="float64"),
        np.asarray(expected, dtype="float64"),
        rtol=tol,
        atol=tol,
        equal_nan=True,
    )


def month_frame(frame: pd.DataFrame, column: str = "month_start") -> pd.DataFrame:
    out = frame.copy()
    out[column] = pd.to_datetime(out[column])
    return out.sort_values(column).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Flows / NNA
# ---------------------------------------------------------------------------


def test_monthly_flows_reconcile_to_fact(query) -> None:
    fact = query(
        """
        SELECT d.month_start,
               SUM(CASE WHEN f.is_net_new AND f.amount_inr > 0 THEN f.amount_inr ELSE 0 END) AS inflows,
               SUM(CASE WHEN f.is_net_new AND f.amount_inr < 0 THEN -f.amount_inr ELSE 0 END) AS outflows,
               SUM(CASE WHEN f.is_net_new THEN f.amount_inr ELSE 0 END) AS nna
        FROM analytics.fact_flows f
        JOIN analytics.dim_date d ON d.date_key = f.date_key
        GROUP BY 1 ORDER BY 1
        """
    )
    flows = month_frame(query("SELECT * FROM analytics.kpi_monthly_flows"))
    assert len(flows) == len(fact)
    assert close(flows["inflows_inr"], fact["inflows"])
    assert close(flows["outflows_inr"], fact["outflows"])
    assert close(flows["net_new_assets_inr"], fact["nna"])
    assert (flows["inflows_inr"] >= 0).all()
    assert (flows["outflows_inr"] >= 0).all()
    assert close(flows["nna_check_inr"], flows["net_new_assets_inr"])
    assert close(flows["net_new_assets_inr"], flows["inflows_inr"] - flows["outflows_inr"])


def test_flow_window_functions_are_correct(query) -> None:
    flows = month_frame(query("SELECT * FROM analytics.kpi_monthly_flows"))
    nna = flows["net_new_assets_inr"]

    assert close(flows["running_nna_inr"], nna.cumsum())
    assert close(flows["nna_ltm_inr"], nna.rolling(12, min_periods=1).sum())
    assert flows["prior_month_nna_inr"].iloc[0] is None or pd.isna(
        flows["prior_month_nna_inr"].iloc[0]
    )
    assert close(flows["prior_month_nna_inr"].iloc[1:], nna.shift(1).iloc[1:])
    assert flows["nna_mom_change_inr"].iloc[0] is None or pd.isna(
        flows["nna_mom_change_inr"].iloc[0]
    )
    assert close(flows["nna_mom_change_inr"].iloc[1:], (nna - nna.shift(1)).iloc[1:])
    expected_pct = 100.0 * (nna - nna.shift(1)) / nna.shift(1)
    assert close(flows["nna_mom_pct"].iloc[1:], expected_pct.iloc[1:], tol=0.01)

    for year, group in flows.groupby("calendar_year"):
        assert close(group["nna_ytd_inr"], group["net_new_assets_inr"].cumsum())


def test_flow_type_nna_sums_to_monthly_nna(query) -> None:
    flows = month_frame(query("SELECT * FROM analytics.kpi_monthly_flows"))
    types = query(
        """
        SELECT month_start, SUM(nna_inr) AS nna
        FROM analytics.kpi_flow_types GROUP BY 1 ORDER BY 1
        """
    ).rename(columns={"month_start": "month_start"})
    types = month_frame(types)
    assert close(types["nna"], flows["net_new_assets_inr"])


# ---------------------------------------------------------------------------
# Assets, fee share and channel mix
# ---------------------------------------------------------------------------


def test_monthly_assets_reconcile_and_fee_share_formula(query) -> None:
    fact = query(
        """
        SELECT d.month_start,
               SUM(f.total_assets_inr) AS total,
               SUM(CASE WHEN f.is_fee_based THEN f.total_assets_inr ELSE 0 END) AS fee
        FROM analytics.fact_monthly_assets f
        JOIN analytics.dim_date d ON d.date_key = f.month_date_key
        GROUP BY 1 ORDER BY 1
        """
    )
    assets = month_frame(query("SELECT * FROM analytics.kpi_monthly_assets"))
    assert len(assets) == len(fact)
    assert close(assets["total_assets_inr"], fact["total"])
    assert close(assets["fee_based_assets_inr"], fact["fee"])
    assert close(
        assets["non_fee_based_assets_inr"],
        assets["total_assets_inr"] - assets["fee_based_assets_inr"],
    )
    expected_share = 100 * assets["fee_based_assets_inr"] / assets["total_assets_inr"]
    assert close(assets["fee_based_share_pct"], expected_share)
    assert ((assets["fee_based_share_pct"] >= 0) & (assets["fee_based_share_pct"] <= 100)).all()
    assert assets["estimated_fee_revenue_inr"].notna().all()
    assert (assets["estimated_fee_revenue_inr"] >= 0).all()
    assert close(
        assets["avg_assets_per_client_inr"],
        assets["total_assets_inr"] / assets["clients_with_assets"],
    )
    assert close(
        assets["fee_based_share_mom_pp"].iloc[1:],
        (assets["fee_based_share_pct"] - assets["fee_based_share_pct"].shift(1)).iloc[1:],
    )
    assert close(
        assets["fee_based_share_3m_avg_pct"],
        assets["fee_based_share_pct"].rolling(3, min_periods=1).mean(),
    )
    expected_mom_pct = (
        100.0
        * (assets["total_assets_inr"] - assets["total_assets_inr"].shift(1))
        / assets["total_assets_inr"].shift(1)
    )
    assert close(assets["assets_mom_pct"].iloc[1:], expected_mom_pct.iloc[1:])


def test_channel_mix_shares_and_nna_reconcile(query) -> None:
    channels = month_frame(query("SELECT * FROM analytics.kpi_channel_mix"))
    by_month = channels.groupby("month_start", as_index=False).agg(
        assets=("total_assets_inr", "sum"),
        asset_share=("assets_share_pct", "sum"),
        clients=("clients", "sum"),
        client_share=("clients_share_pct", "sum"),
    )
    totals = month_frame(query("SELECT * FROM analytics.kpi_monthly_assets"))[
        ["month_start", "total_assets_inr", "clients_with_assets"]
    ]
    merged = by_month.merge(totals, on="month_start")
    assert close(merged["assets"], merged["total_assets_inr"])
    assert close(merged["asset_share"], 100.0, tol=0.05)
    assert close(merged["clients"], merged["clients_with_assets"])
    assert close(merged["client_share"], 100.0, tol=0.05)

    nna_fact = query(
        """
        SELECT d.month_start, f.channel_key, SUM(f.amount_inr) AS nna
        FROM analytics.fact_flows f
        JOIN analytics.dim_date d ON d.date_key = f.date_key
        WHERE f.is_net_new
        GROUP BY 1, 2
        """
    )
    nna_fact["month_start"] = pd.to_datetime(nna_fact["month_start"])
    merged = channels.merge(
        nna_fact, on=["month_start", "channel_key"], how="left", suffixes=("", "_fact")
    ).fillna({"nna": 0})
    assert close(merged["nna_inr"], merged["nna"])


def test_channel_ltm_nna_is_trailing_twelve_months(query) -> None:
    channels = month_frame(query("SELECT * FROM analytics.kpi_channel_mix"))
    for channel_key, group in channels.groupby("channel_key"):
        group = group.sort_values("month_start")
        expected = group["nna_inr"].rolling(12, min_periods=1).sum()
        assert close(group["nna_ltm_inr"], expected), channel_key


# ---------------------------------------------------------------------------
# Migration and funnel
# ---------------------------------------------------------------------------


def test_migration_summary_matches_cohorts_and_definition(query, built) -> None:
    cohorts = query("SELECT * FROM analytics.kpi_migration_to_advice")
    summary = query("SELECT * FROM analytics.kpi_migration_summary")
    assert len(summary) == 1
    assert close(summary["eligible_clients"].sum(), cohorts["eligible_clients"].sum())
    assert close(summary["migrated_clients"].sum(), cohorts["migrated_clients"].sum())
    expected_rate = 100 * summary["migrated_clients"] / summary["eligible_clients"]
    assert close(summary["migration_rate_pct"], expected_rate, tol=0.01)

    cutoff = pd.Timestamp(built.end_month) - pd.Timedelta(days=90)
    clients = query("SELECT * FROM analytics.dim_client")
    eligible = clients[
        (clients["channel_code"] == "DIGITAL")
        & (pd.to_datetime(clients["onboarding_date"]) <= cutoff)
    ]
    assert len(eligible) == int(summary["eligible_clients"].iloc[0])

    plans = query(
        """
        SELECT DISTINCT client_key FROM analytics.fact_engagement
        WHERE event_type = 'plan_created'
        """
    )
    migrated = eligible[eligible["client_key"].isin(plans["client_key"])]
    assert len(migrated) == int(summary["migrated_clients"].iloc[0])


def test_advice_funnel_reconciles_to_dimensions(query) -> None:
    funnel = query("SELECT * FROM analytics.kpi_advice_funnel")
    clients = query("SELECT COUNT(*) AS n FROM analytics.dim_client").iloc[0, 0]
    assert funnel["clients"].sum() == clients
    assert (funnel["engaged_clients"] <= funnel["clients"]).all()
    assert (funnel["planned_clients"] <= funnel["engaged_clients"]).all()
    assert (funnel["fee_based_clients"] <= funnel["clients"]).all()
    assert close(
        funnel["engagement_rate_pct"],
        100 * funnel["engaged_clients"] / funnel["clients"],
        tol=0.01,
    )
    assert close(
        funnel["planning_rate_pct"],
        100 * funnel["planned_clients"] / funnel["clients"],
        tol=0.01,
    )
    assert close(
        funnel["fee_based_rate_pct"],
        100 * funnel["fee_based_clients"] / funnel["clients"],
        tol=0.01,
    )


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def test_retention_rates_and_observed_flags(query, built) -> None:
    retention = query("SELECT * FROM analytics.kpi_cohort_retention")
    cohorts = query("SELECT cohort_month, COUNT(*) AS n FROM analytics.dim_client GROUP BY 1")
    cohorts["cohort_month"] = pd.to_datetime(cohorts["cohort_month"])
    retention["cohort_month"] = pd.to_datetime(retention["cohort_month"])
    merged = retention.merge(cohorts, on="cohort_month")
    assert close(merged["cohort_size"], merged["n"])

    observed = retention[retention["is_observed"]]
    assert len(observed) > 0
    assert observed["retained_clients"].notna().all()
    assert close(
        observed["retention_rate_pct"],
        100 * observed["retained_clients"] / observed["cohort_size"],
        tol=0.01,
    )
    assert ((observed["retention_rate_pct"] >= 0) & (observed["retention_rate_pct"] <= 100)).all()
    assert (observed["retained_clients"] <= observed["cohort_size"]).all()
    assert observed["retained_clients"].ge(0).all()

    unobserved = retention[~retention["is_observed"]]
    assert unobserved["retained_clients"].isna().all()
    assert unobserved["retention_rate_pct"].isna().all()

    start = pd.Timestamp(built.month_ends[0]).replace(day=1)
    end = pd.Timestamp(built.end_month).replace(day=1)
    observed_months = observed.apply(
        lambda row: (
            pd.Timestamp(row["cohort_month"])
            + pd.DateOffset(months=int(row["months_since_onboarding"]))
        ),
        axis=1,
    )
    assert observed_months.between(start, end).all()


def test_retention_summary_is_weighted_observed_12m(query) -> None:
    summary = query("SELECT * FROM analytics.kpi_retention_summary")
    observed = query(
        """
        SELECT * FROM analytics.kpi_cohort_retention
        WHERE months_since_onboarding = 12 AND is_observed
        """
    )
    assert len(summary) == 1
    assert close(summary["eligible_cohort_clients"], observed["cohort_size"].sum())
    assert close(summary["retained_clients"], observed["retained_clients"].sum())
    assert close(
        summary["retention_12m_pct"],
        100 * observed["retained_clients"].sum() / observed["cohort_size"].sum(),
        tol=0.01,
    )


# ---------------------------------------------------------------------------
# Advisor productivity
# ---------------------------------------------------------------------------


def test_advisor_rank_and_quartiles(query) -> None:
    advisors = query("SELECT * FROM analytics.kpi_advisor_productivity")
    assert len(advisors) == 30
    assert advisors["advisor_key"].nunique() == 30
    assert set(advisors["productivity_quartile"].unique()) == {1, 2, 3, 4}
    assert advisors["nna_rank"].min() == 1
    assert advisors.sort_values("nna_rank")["nna_ltm_inr"].is_monotonic_decreasing
    assert advisors.groupby("productivity_quartile")["nna_ltm_inr"].mean().is_monotonic_decreasing
    assert close(advisors["pct_of_book"].sum(), 100.0, tol=0.1)
    assert advisors["nna_gap_to_next_inr"].iloc[0] is None or pd.isna(
        advisors.sort_values("nna_rank")["nna_gap_to_next_inr"].iloc[0]
    )
    assert close(
        advisors["fee_based_share_pct"],
        100 * advisors["fee_based_assets_inr"] / advisors["total_assets_inr"],
    )
    assert close(
        advisors["assets_per_client_inr"],
        advisors["total_assets_inr"] / advisors["clients"],
    )
    assert close(
        advisors["nna_per_client_inr"],
        advisors["nna_ltm_inr"] / advisors["clients"],
    )

    top_advisors = query("SELECT * FROM analytics.kpi_top_advisors")
    assert len(top_advisors) == 10
    assert list(top_advisors["nna_rank"]) == list(range(1, 11))
    assert top_advisors.sort_values("nna_rank")["nna_ltm_inr"].is_monotonic_decreasing


def test_advisor_monthly_windows_and_asof_attribution(query) -> None:
    advisors = query("SELECT advisor_name FROM analytics.kpi_advisor_productivity ORDER BY nna_rank")
    name = advisors.iloc[0, 0]
    monthly = query("SELECT * FROM analytics.kpi_advisor_monthly WHERE advisor_name = ?", [name])
    monthly = month_frame(monthly)
    assert len(monthly) > 0
    expected_running = monthly["nna_inr"].cumsum()
    assert close(monthly["running_nna_inr"], expected_running)
    assert close(monthly["prior_month_assets_inr"].iloc[1:], monthly["total_assets_inr"].shift(1).iloc[1:])
    assert monthly.groupby("month_start")["assets_rank"].apply(lambda s: s.between(1, 30).all()).all()

    all_monthly = month_frame(query(
        """
        SELECT month_start,
               SUM(total_assets_inr) AS assets,
               SUM(nna_inr) AS nna
        FROM analytics.kpi_advisor_monthly
        GROUP BY 1 ORDER BY 1
        """
    ))
    monthly_assets = month_frame(query("SELECT month_start, total_assets_inr FROM analytics.kpi_monthly_assets ORDER BY 1"))
    monthly_flows = month_frame(query("SELECT month_start, net_new_assets_inr FROM analytics.kpi_monthly_flows ORDER BY 1"))
    assert close(all_monthly["assets"], monthly_assets["total_assets_inr"])
    assert close(all_monthly["nna"], monthly_flows["net_new_assets_inr"])


def test_client_rankings_and_segments(query) -> None:
    clients = query("SELECT * FROM analytics.kpi_client_value")
    top = query("SELECT * FROM analytics.kpi_top_clients")
    assert top["asset_rank"].min() == 1
    assert len(top) == 25
    assert set(top["asset_rank"]) == set(range(1, 26))
    assert top.sort_values("asset_rank")["total_assets_inr"].is_monotonic_decreasing
    assert top["asset_decile"].between(1, 10).all()
    assert top["client_key"].isin(clients["client_key"]).all()
    assert close(clients["pct_of_book"].sum(), 100.0, tol=0.1)

    segments = query("SELECT * FROM analytics.kpi_client_segments")
    latest = query("SELECT * FROM analytics.kpi_monthly_assets ORDER BY month_start DESC LIMIT 1").iloc[0]
    assert segments["clients"].sum() == len(clients)
    assert close(segments["total_assets_inr"].sum(), latest["total_assets_inr"])
    assert close(segments["assets_share_pct"].sum(), 100.0, tol=0.1)
    assert close(
        segments["fee_based_share_pct"],
        100 * segments["fee_based_assets_inr"] / segments["total_assets_inr"],
        tol=0.01,
    )
    assert close(
        segments["avg_assets_per_client_inr"],
        segments["total_assets_inr"] / segments["clients"],
        tol=0.01,
    )
    latest_flows = query("SELECT nna_ltm_inr FROM analytics.kpi_monthly_flows ORDER BY month_start DESC LIMIT 1").iloc[0]
    assert close(segments["nna_ltm_inr"].sum(), latest_flows["nna_ltm_inr"])


# ---------------------------------------------------------------------------
# Engagement and executive consistency
# ---------------------------------------------------------------------------


def test_engagement_views_reconcile(query) -> None:
    summary = month_frame(query("SELECT * FROM analytics.kpi_engagement_summary"))
    monthly = query("SELECT * FROM analytics.kpi_engagement_monthly")
    by_month = monthly.groupby("month_start", as_index=False).agg(
        events=("events", "sum"),
        total_minutes=("total_minutes", "sum"),
    )
    by_month["month_start"] = pd.to_datetime(by_month["month_start"])
    merged = summary.merge(by_month, on="month_start")
    assert close(merged["events_x"], merged["events_y"])
    assert close(merged["total_minutes_x"], merged["total_minutes_y"])
    assert (
        summary["events"]
        >= summary["advice_meetings"] + summary["plans_created"] + summary["plan_reviews"]
    ).all()
    assert (summary["engaged_clients"] <= summary["events"]).all()

    fact_totals = query("SELECT COUNT(*) AS events, SUM(duration_minutes) AS minutes FROM analytics.fact_engagement").iloc[0]
    assert int(summary["events"].sum()) == int(fact_totals["events"])
    assert close(summary["total_minutes"].sum(), fact_totals["minutes"])


def test_executive_overview_is_consistent(query) -> None:
    exec_row = query("SELECT * FROM analytics.kpi_exec_overview").iloc[0]
    latest_assets = query(
        "SELECT * FROM analytics.kpi_monthly_assets ORDER BY month_start DESC LIMIT 1"
    ).iloc[0]
    latest_flows = query(
        "SELECT * FROM analytics.kpi_monthly_flows ORDER BY month_start DESC LIMIT 1"
    ).iloc[0]
    migration = query("SELECT * FROM analytics.kpi_migration_summary").iloc[0]
    retention = query("SELECT * FROM analytics.kpi_retention_summary").iloc[0]

    assert exec_row["as_of_month"] == latest_assets["month_start"]
    assert close(exec_row["total_assets_inr"], latest_assets["total_assets_inr"])
    assert close(exec_row["fee_based_assets_inr"], latest_assets["fee_based_assets_inr"])
    assert close(exec_row["fee_based_share_pct"], latest_assets["fee_based_share_pct"])
    assert exec_row["active_clients"] == latest_assets["clients_with_assets"]
    assert exec_row["active_accounts"] == latest_assets["accounts_with_assets"]
    assert close(exec_row["latest_month_nna_inr"], latest_flows["net_new_assets_inr"])
    assert close(exec_row["nna_ltm_inr"], latest_flows["nna_ltm_inr"])
    assert close(exec_row["nna_ytd_inr"], latest_flows["nna_ytd_inr"])
    assert close(exec_row["migration_rate_pct"], migration["migration_rate_pct"])
    assert close(exec_row["retention_12m_pct"], retention["retention_12m_pct"])
    assert exec_row["advisors"] == 30
    expected_end = pd.Timestamp(latest_assets["month_start"]) + pd.offsets.MonthEnd(0)
    assert pd.Timestamp(exec_row["as_of_month_end"]) == expected_end

    as_of_end = exec_row["as_of_month_end"]
    ltm_start = pd.Timestamp(as_of_end) - pd.DateOffset(years=1)
    expected_plans = query(
        """
        SELECT COUNT(*) AS n FROM analytics.fact_engagement
        WHERE event_type = 'plan_created'
          AND event_date > ? AND event_date <= ?
        """,
        [ltm_start.date(), as_of_end],
    ).iloc[0, 0]
    assert int(exec_row["plans_created_ltm"]) == int(expected_plans)

    expected_meetings = query(
        """
        SELECT COUNT(*) AS n FROM analytics.fact_engagement
        WHERE event_type = 'meeting'
          AND event_date > ? AND event_date <= ?
        """,
        [ltm_start.date(), as_of_end],
    ).iloc[0, 0]
    assert int(exec_row["advice_meetings_ltm"]) == int(expected_meetings)

    expected_fee = query(
        """
        SELECT COALESCE(SUM(estimated_fee_revenue_inr), 0) AS total
        FROM analytics.fact_monthly_assets
        WHERE month_end > ? AND month_end <= ?
        """,
        [ltm_start.date(), as_of_end],
    ).iloc[0, 0]
    assert close(exec_row["estimated_fee_revenue_ltm"], expected_fee)

    adv_roll = query(
        """
        SELECT SUM(plans_ltm) AS plans,
               SUM(meetings_ltm) AS meetings,
               SUM(estimated_fee_revenue_ltm) AS fees,
               SUM(nna_ltm_inr) AS nna
        FROM analytics.kpi_advisor_productivity
        """
    ).iloc[0]
    assert int(adv_roll["plans"]) == int(exec_row["plans_created_ltm"])
    assert int(adv_roll["meetings"]) == int(exec_row["advice_meetings_ltm"])
    assert close(adv_roll["fees"], exec_row["estimated_fee_revenue_ltm"])
    assert close(adv_roll["nna"], exec_row["nna_ltm_inr"])


def test_advisor_meetings_per_client_formula(query) -> None:
    adv = query("SELECT advisor_key, clients, meetings_ltm, meetings_per_client FROM analytics.kpi_advisor_productivity")
    for _, row in adv.iterrows():
        if row["clients"] == 0:
            assert pd.isna(row["meetings_per_client"])
        else:
            expected = float(row["meetings_ltm"]) / float(row["clients"])
            assert close(row["meetings_per_client"], expected, tol=1e-4)


def test_client_ltm_nna_population_reconciliation(query) -> None:
    # Population reconciliation: clients in kpi_client_value are those present in the latest-month asset snapshot.
    # Total LTM NNA in kpi_exec_overview includes all clients (including those who closed earlier with net outflows).
    matched_sum = query("SELECT SUM(nna_ltm_inr) AS s FROM analytics.kpi_client_value").iloc[0]["s"]
    exec_nna = query("SELECT nna_ltm_inr FROM analytics.kpi_exec_overview").iloc[0]["nna_ltm_inr"]

    # Excluded clients are those with LTM flows whose accounts closed prior to the latest month
    excluded_nna_query = """
    WITH latest AS (SELECT MAX(month_end) AS max_month FROM analytics.fact_monthly_assets),
    book_clients AS (
        SELECT DISTINCT client_key FROM analytics.fact_monthly_assets
        WHERE month_end = (SELECT max_month FROM latest)
    ),
    excluded_flows AS (
        SELECT COALESCE(SUM(f.amount_inr), 0) AS excluded_nna
        FROM analytics.fact_flows f
        CROSS JOIN latest l
        WHERE f.is_net_new
          AND f.flow_date > CAST(l.max_month - INTERVAL 12 MONTH AS DATE)
          AND f.flow_date <= l.max_month
          AND f.client_key NOT IN (SELECT client_key FROM book_clients)
    )
    SELECT excluded_nna FROM excluded_flows
    """
    excluded_nna = query(excluded_nna_query).iloc[0]["excluded_nna"]
    assert close(matched_sum + excluded_nna, exec_nna, tol=1e-2)

