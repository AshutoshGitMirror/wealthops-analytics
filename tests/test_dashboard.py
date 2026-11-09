"""Dashboard data-access, query helpers, and AppTest workspace rendering tests.

All read-only query helpers and full headless workspace interactions (navigation
and NLQ form submissions) are exercised against the test warehouse.
"""

from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from wealthops.dashboard import data as d

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db(built):
    return built.db_path


def test_dashboard_app_compiles() -> None:
    py_compile.compile(str(ROOT / "dashboard" / "app.py"), doraise=True)


def test_months_exec_and_manifest(db, built) -> None:
    months = d.load_months(db)
    assert len(months) == built.months
    assert months[0] < months[-1]
    assert d.load_months.__module__ == "wealthops.dashboard.data"

    exec_row = d.load_exec(db)
    assert len(exec_row) == 1
    for column in (
        "total_assets_inr",
        "fee_based_share_pct",
        "active_clients",
        "nna_ltm_inr",
        "migration_rate_pct",
        "retention_12m_pct",
        "as_of_month_end",
    ):
        assert column in exec_row.columns

    manifest = d.load_manifest(built.data_dir)
    assert manifest["seed"] == built.seed
    assert manifest["clients"] == built.n_clients


def test_counts_and_quality_are_visible(db) -> None:
    counts = d.load_counts(db).set_index("metric")["value"]
    assert counts["clients"] == 1_200
    assert counts["checks passed"] == counts["KPI checks"]
    assert counts["KPI checks"] >= 40

    quality = d.load_quality(db)
    assert len(quality) >= 40
    assert (quality["status"] == "PASS").all()


def test_monthly_flow_and_asset_queries(db) -> None:
    months = d.load_months(db)
    flows = d.load_monthly_flows(db, months[0], months[-1])
    assets = d.load_monthly_assets(db, months[0], months[-1])
    assert len(flows) == len(months)
    assert len(assets) == len(months)
    assert flows["month_start"].is_monotonic_increasing
    assert assets["month_start"].is_monotonic_increasing

    partial = d.load_monthly_flows(db, months[-3], months[-1])
    assert len(partial) == 3


def test_channel_and_flow_type_queries(db, built) -> None:
    months = d.load_months(db)
    channels = d.load_channel_options(db)
    assert len(channels) == built.n_channels
    mix = d.load_channel_mix(db, months[0], months[-1])
    assert set(mix["channel_name"]) == set(channels)
    filtered = d.load_channel_mix(db, months[0], months[-1], [channels[0]])
    assert set(filtered["channel_name"]) == {channels[0]}

    flow_types = d.load_flow_types(db, months[0], months[-1])
    assert len(flow_types) > 0
    assert {"flow_type", "direction", "nna_inr"}.issubset(flow_types.columns)


def test_advisor_queries(db) -> None:
    advisors = d.load_advisor_productivity(db)
    assert len(advisors) == 30
    assert advisors["nna_rank"].is_monotonic_increasing
    top = d.load_top_advisors(db, limit=5)
    assert len(top) == 5
    assert top["nna_rank"].min() == 1
    assert list(top["nna_rank"]) == list(range(1, 6))
    options = d.load_advisor_options(db)
    assert len(options) == 30
    monthly = d.load_advisor_monthly(db, options[0])
    assert len(monthly) > 0
    assert {"month_start", "total_assets_inr", "nna_inr"}.issubset(monthly.columns)


def test_client_and_segment_queries(db) -> None:
    segments = d.load_client_segments(db)
    assert len(segments) > 0
    top = d.load_top_clients(db, limit=5)
    assert len(top) == 5
    assert top["asset_rank"].min() == 1

    options = d.load_segment_options(db)
    assert len(options) > 0
    assert set(segments["segment"]) == set(options)


def test_migration_funnel_and_engagement_queries(db) -> None:
    funnel = d.load_funnel(db)
    assert len(funnel) == 3
    assert {
        "channel_name",
        "clients",
        "engaged_clients",
        "planned_clients",
        "fee_based_clients",
        "planning_rate_pct",
    }.issubset(funnel.columns)
    assert (funnel["planned_clients"] <= funnel["engaged_clients"]).all()
    assert (funnel["engaged_clients"] <= funnel["clients"]).all()

    migration = d.load_migration_summary(db)
    assert len(migration) == 1
    assert {"channel_name", "eligible_clients", "migrated_clients", "migration_rate_pct"}.issubset(migration.columns)
    assert migration["channel_name"].iloc[0] == "Digital Direct"
    assert migration["migrated_clients"].iloc[0] <= migration["eligible_clients"].iloc[0]
    assert 0 <= migration["migration_rate_pct"].iloc[0] <= 100

    cohorts = d.load_migration_cohorts(db)
    assert len(cohorts) > 0
    assert {"cohort_month", "eligible_clients", "migrated_clients", "migration_rate_pct"}.issubset(cohorts.columns)

    months = d.load_months(db)
    engagement = d.load_engagement(db, months[0], months[-1])
    assert len(engagement) == len(months)
    assert {
        "month_start",
        "events",
        "engaged_clients",
        "advice_meetings",
        "plans_created",
    }.issubset(engagement.columns)


def test_retention_query_honours_observed_rows(db) -> None:
    months = d.load_months(db)
    retention = d.load_retention(db, months[0], months[-1])
    assert len(retention) > 0
    assert retention["is_observed"].all()
    assert retention["retention_rate_pct"].notna().all()
    assert (retention["retention_rate_pct"] >= 0).all()
    assert (retention["retention_rate_pct"] <= 100).all()
    assert (retention["retained_clients"] <= retention["cohort_size"]).all()
    assert {"cohort_month", "months_since_onboarding", "cohort_size", "retained_clients"}.issubset(retention.columns)


def test_dashboard_all_workspaces_render(db, monkeypatch) -> None:
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("WEALTHOPS_DB_PATH", str(db))
    at = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception

    workspaces = [
        "Flows & channels",
        "Advisor book",
        "Client cohorts",
        "Data quality",
        "Ask the data",
    ]
    for ws in workspaces:
        at.sidebar.radio[0].set_value(ws).run()
        assert not at.exception

    # Exercise governed NL query execution in the "Ask the data" workspace
    at.form[0].text_input[0].set_value("Show net new assets by month")
    at.form[0].form_submit_button[0].click().run()
    assert not at.exception
    assert len(at.code) > 0
    assert len(at.dataframe) > 0

    # Also test an invalid query handling gracefully in AppTest
    at.form[0].text_input[0].set_value("Nonexistent query 99999")
    at.form[0].form_submit_button[0].click().run()
    assert not at.exception
    assert len(at.error) > 0

