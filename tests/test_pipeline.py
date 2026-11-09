"""End-to-end pipeline, manifest, export and quality tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from wealthops.config import Settings
from wealthops.db import connect, relation_exists
from wealthops.pipeline import EXPORT_VIEWS, status


def test_manifest_matches_settings(manifest: dict, built: Settings) -> None:
    assert manifest["seed"] == built.seed
    assert manifest["clients"] == built.n_clients
    assert manifest["advisors"] == built.n_advisors
    assert manifest["channels"] == built.n_channels
    assert manifest["months"] == built.months
    assert manifest["start_month"] == built.start_month.isoformat()
    assert manifest["end_month"] == built.end_month.isoformat()
    assert "synthetic" in manifest["disclaimer"].lower()
    assert "no morgan stanley affiliation" in manifest["disclaimer"].lower()


def test_manifest_row_counts_match_operational_tables(manifest: dict, query) -> None:
    expected = manifest["row_counts"]
    observed = {
        "channel": int(query("SELECT COUNT(*) AS n FROM ops.channel").iloc[0, 0]),
        "advisor": int(query("SELECT COUNT(*) AS n FROM ops.advisor").iloc[0, 0]),
        "client": int(query("SELECT COUNT(*) AS n FROM ops.client").iloc[0, 0]),
        "account": int(query("SELECT COUNT(*) AS n FROM ops.account").iloc[0, 0]),
        "advisor_assignment": int(
            query("SELECT COUNT(*) AS n FROM ops.advisor_assignment").iloc[0, 0]
        ),
        "transaction": int(query("SELECT COUNT(*) AS n FROM ops.transaction").iloc[0, 0]),
        "monthly_asset_snapshot": int(
            query("SELECT COUNT(*) AS n FROM ops.monthly_asset_snapshot").iloc[0, 0]
        ),
        "engagement_event": int(
            query("SELECT COUNT(*) AS n FROM ops.engagement_event").iloc[0, 0]
        ),
    }
    assert observed == {key: int(value) for key, value in expected.items()}


def test_all_declared_relations_exist(con) -> None:
    for relation in (
        "ops.client",
        "ops.account",
        "ops.transaction",
        "ops.monthly_asset_snapshot",
        "ops.engagement_event",
        "ops.advisor_assignment",
        "ops.scenario_config",
        "analytics.dim_date",
        "analytics.dim_client",
        "analytics.dim_account",
        "analytics.dim_advisor",
        "analytics.dim_channel",
        "analytics.dim_advisor_assignment",
        "analytics.fact_flows",
        "analytics.fact_monthly_assets",
        "analytics.fact_engagement",
        "analytics.kpi_exec_overview",
    ):
        assert relation_exists(con, relation), relation


def test_fact_row_counts_reconcile(query) -> None:
    pairs = [
        ("analytics.fact_flows", "ops.transaction"),
        ("analytics.fact_monthly_assets", "ops.monthly_asset_snapshot"),
        ("analytics.fact_engagement", "ops.engagement_event"),
    ]
    for fact, source in pairs:
        fact_n = int(query(f"SELECT COUNT(*) AS n FROM {fact}").iloc[0, 0])
        source_n = int(query(f"SELECT COUNT(*) AS n FROM {source}").iloc[0, 0])
        assert fact_n == source_n, (fact, source)


def test_scenario_config_is_parameter_aware(query) -> None:
    config = query("SELECT key, value FROM ops.scenario_config").set_index("key")["value"]
    assert int(config["expected_clients"]) == 1_200
    assert int(config["expected_advisors"]) == 30
    assert int(config["expected_channels"]) == 3
    assert int(config["expected_months"]) == 24
    assert int(config["expected_min_transactions"]) == 12_000


def test_quality_checks_all_pass(query) -> None:
    quality = query("SELECT * FROM analytics.v_data_quality")
    assert len(quality) >= 40
    assert set(quality["status"].unique()) == {"PASS"}
    assert quality["check_name"].is_unique
    assert quality["category"].notna().all()
    assert set(quality["category"].unique()) == {
        "Uniqueness",
        "Referential integrity",
        "Validity",
        "SCD2",
        "Reconciliation",
        "Seeded invariant",
    }


def test_status_matches_quality(query, built: Settings) -> None:
    info = status(built)
    assert info["exists"] is True
    assert info["quality"]["failed"] == 0
    assert info["quality"]["passed"] == info["quality"]["checks"]
    assert info["counts"]["clients"] == built.n_clients
    assert info["counts"]["advisors"] == built.n_advisors


def test_exports_are_written_and_nonempty(built: Settings, query) -> None:
    for view, filename in EXPORT_VIEWS.items():
        path = built.export_dir / filename
        assert path.exists(), path
        frame = pd.read_csv(path)
        assert len(frame) > 0, view
        expected = query(f"SELECT COUNT(*) AS n FROM analytics.{view}").iloc[0, 0]
        assert len(frame) == expected, f"{filename} row count mismatch: {len(frame)} vs {expected}"
    exported = sorted(p.name for p in built.export_dir.glob("*.csv"))
    assert exported == sorted(EXPORT_VIEWS.values())


def test_raw_parquet_files_exist(built: Settings, manifest: dict) -> None:
    expected = set(manifest["files"].values())
    present = {
        str(path.relative_to(built.data_dir)) for path in built.raw_dir.glob("*.parquet")
    }
    assert expected == present


def test_duplicate_primary_keys_are_absent(query) -> None:
    for table, key in (
        ("ops.client", "client_id"),
        ("ops.account", "account_id"),
        ("ops.advisor", "advisor_id"),
        ("ops.transaction", "transaction_id"),
        ("ops.monthly_asset_snapshot", "snapshot_id"),
        ("ops.engagement_event", "event_id"),
        ("ops.advisor_assignment", "assignment_id"),
    ):
        duplicates = query(
            f"SELECT COUNT(*) AS n FROM (SELECT {key} FROM {table} GROUP BY 1 HAVING COUNT(*) > 1)"
        ).iloc[0, 0]
        assert int(duplicates) == 0, table


def test_monthly_window_is_complete(query, built: Settings) -> None:
    months = query(
        "SELECT DISTINCT month_start FROM analytics.fact_monthly_assets ORDER BY 1"
    )["month_start"].tolist()
    assert len(months) == built.months
    assert months[0] == pd.Timestamp(built.month_ends[0]).replace(day=1)
    assert months[-1] == pd.Timestamp(built.end_month).replace(day=1)


def test_connection_enforces_laptop_limits(tmp_path: Path, built: Settings) -> None:
    from wealthops.db import connect

    con_ro = connect(built.db_path, read_only=True)
    try:
        threads_ro = con_ro.execute("SELECT current_setting('threads')").fetchone()[0]
        assert int(threads_ro) == 2
    finally:
        con_ro.close()

    rw_db = tmp_path / "test_rw.duckdb"
    con_rw = connect(rw_db, read_only=False)
    try:
        threads_rw = con_rw.execute("SELECT current_setting('threads')").fetchone()[0]
        assert int(threads_rw) == 2
    finally:
        con_rw.close()


def test_status_on_empty_and_missing_database(tmp_path: Path) -> None:
    # Missing database
    missing_settings = Settings(data_dir=tmp_path / "missing", export_dir=tmp_path / "exports")
    res_missing = status(missing_settings)
    assert res_missing["exists"] is False

    # Empty database file created without tables
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir(parents=True, exist_ok=True)
    empty_settings = Settings(data_dir=empty_dir, export_dir=empty_dir / "exports")
    empty_con = connect(empty_settings.db_path)
    empty_con.close()

    res_empty = status(empty_settings)
    assert res_empty["exists"] is True
    assert res_empty["counts"] == {}
    assert res_empty["quality"] is None
