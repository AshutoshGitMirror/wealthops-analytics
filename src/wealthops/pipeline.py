"""End-to-end pipeline: generate -> load -> transform -> quality -> export."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Settings
from .db import (
    connect,
    drop_database_files,
    fetch_df,
    fetch_one,
    relation_exists,
    run_sql_dir,
    run_sql_file,
)
from .generate import dataset_fingerprint, generate_data, write_raw


EXPORT_VIEWS = {
    "kpi_exec_overview": "kpi_exec_overview.csv",
    "kpi_monthly_flows": "kpi_monthly_flows.csv",
    "kpi_monthly_assets": "kpi_monthly_assets.csv",
    "kpi_channel_mix": "kpi_channel_mix.csv",
    "kpi_migration_to_advice": "kpi_migration_to_advice.csv",
    "kpi_migration_summary": "kpi_migration_summary.csv",
    "kpi_cohort_retention": "kpi_cohort_retention.csv",
    "kpi_advisor_productivity": "kpi_advisor_productivity.csv",
    "kpi_client_value": "kpi_client_value.csv",
    "kpi_client_segments": "kpi_client_segments.csv",
    "kpi_engagement_summary": "kpi_engagement_summary.csv",
    "v_data_quality": "data_quality.csv",
}

TABLE_COUNTS = [
    ("ops.client", "clients"),
    ("ops.advisor", "advisors"),
    ("ops.account", "accounts"),
    ("ops.transaction", "transactions"),
    ("ops.monthly_asset_snapshot", "monthly_snapshots"),
    ("ops.engagement_event", "engagement_events"),
    ("ops.advisor_assignment", "scd2_assignments"),
    ("analytics.fact_flows", "fact_flows"),
    ("analytics.fact_monthly_assets", "fact_monthly_assets"),
    ("analytics.fact_engagement", "fact_engagement"),
]


def apply_seed(settings: Settings, seed: int | None) -> Settings:
    return replace(settings, seed=seed) if seed is not None else settings


def generate(settings: Settings, *, verbose: bool = True) -> dict[str, Any]:
    """Generate parquet files and a manifest.  Returns a small summary dict."""
    settings.ensure_dirs()
    data = generate_data(settings)
    paths = write_raw(data, settings.raw_dir)
    manifest = {
        "scenario": "WealthOps synthetic wealth-management scenario",
        "disclaimer": (
            "All clients, advisors, accounts, transactions and outcomes are synthetic. "
            "No Morgan Stanley affiliation. No real or confidential client data."
        ),
        "seed": settings.seed,
        "clients": settings.n_clients,
        "advisors": settings.n_advisors,
        "channels": settings.n_channels,
        "months": settings.months,
        "start_month": settings.start_month.isoformat(),
        "end_month": settings.end_month.isoformat(),
        "row_counts": {name: int(len(frame)) for name, frame in data.frames().items()},
        "fingerprints": dataset_fingerprint(data),
        "files": {name: str(path.relative_to(settings.data_dir)) for name, path in paths.items()},
    }
    manifest_path = settings.raw_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if verbose:
        print(f"[generate] seed={settings.seed} raw={settings.raw_dir}")
        for name, count in manifest["row_counts"].items():
            print(f"  {name:<24} {count:>8,}")
    return manifest


def reset_database(settings: Settings) -> None:
    drop_database_files(settings.db_path)


def load(settings: Settings, *, verbose: bool = True) -> None:
    """Create the operational schema and load the generated parquet files."""
    settings.ensure_dirs()
    con = connect(settings.db_path)
    try:
        run_sql_file(con, settings.sql_dir / "01_operational_schema.sql")
        run_sql_file(
            con,
            settings.sql_dir / "02_load_operational.sql",
            raw_dir=settings.raw_dir,
        )
        _write_scenario_config(con, settings)
    finally:
        con.close()
    if verbose:
        print(f"[load] operational tables loaded into {settings.db_path}")


def _write_scenario_config(con, settings: Settings) -> None:
    """Persist the declared scenario size for parameter-aware quality checks."""
    manifest_path = settings.raw_dir / "_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    clients = int(manifest.get("clients", settings.n_clients))
    advisors = int(manifest.get("advisors", settings.n_advisors))
    channels = int(manifest.get("channels", settings.n_channels))
    months = int(manifest.get("months", settings.months))
    # The fixture is expected to have a real transaction volume relative to its
    # client count, not a fixed production-sized number.
    min_transactions = max(1_000, clients * 10)
    rows = [
        ("expected_clients", str(clients)),
        ("expected_advisors", str(advisors)),
        ("expected_channels", str(channels)),
        ("expected_months", str(months)),
        ("expected_min_transactions", str(min_transactions)),
        ("seed", str(manifest.get("seed", settings.seed))),
    ]
    con.execute("DELETE FROM ops.scenario_config")
    con.executemany("INSERT INTO ops.scenario_config VALUES (?, ?)", rows)


def transform(settings: Settings, *, verbose: bool = True) -> list[str]:
    """Build dimensions, facts and KPI views from the operational layer."""
    con = connect(settings.db_path)
    executed: list[str] = []
    try:
        for path in sorted(settings.sql_dir.glob("*.sql")):
            if path.name.startswith(("01_", "02_")):
                continue
            run_sql_file(con, path)
            executed.append(path.name)
    finally:
        con.close()
    if verbose:
        print(f"[transform] {len(executed)} SQL files executed")
        for name in executed:
            print(f"  {name}")
    return executed


def run_quality(settings: Settings, *, verbose: bool = True) -> pd.DataFrame:
    con = connect(settings.db_path)
    try:
        run_sql_file(con, settings.sql_dir / "quality" / "checks.sql")
        results = fetch_df(con, "SELECT * FROM analytics.v_data_quality ORDER BY category, check_name")
    finally:
        con.close()
    if verbose:
        failures = results[results["status"] != "PASS"]
        print(f"[quality] {len(results) - len(failures)}/{len(results)} checks passed")
        if len(failures):
            for row in failures.itertuples(index=False):
                print(f"  FAIL {row.check_name}: observed={row.observed} expected={row.expected}")
    return results


def quality_summary(settings: Settings) -> dict[str, Any]:
    con = connect(settings.db_path)
    try:
        row = con.execute(
            """
            SELECT
                COUNT(*) AS checks,
                COUNT(*) FILTER (WHERE status = 'PASS') AS passed,
                COUNT(*) FILTER (WHERE status <> 'PASS') AS failed
            FROM analytics.v_data_quality
            """
        ).fetchone()
    finally:
        con.close()
    checks, passed, failed = (int(x) for x in row)
    return {"checks": checks, "passed": passed, "failed": failed}


def export(settings: Settings, *, verbose: bool = True) -> dict[str, Path]:
    """Export governed KPI views for Excel/BI consumers."""
    settings.ensure_dirs()
    con = connect(settings.db_path, read_only=True)
    outputs: dict[str, Path] = {}
    try:
        for view, filename in EXPORT_VIEWS.items():
            frame = fetch_df(con, f"SELECT * FROM analytics.{view}")
            path = settings.export_dir / filename
            frame.to_csv(path, index=False)
            outputs[view] = path
    finally:
        con.close()
    if verbose:
        print(f"[export] {len(outputs)} CSV files written to {settings.export_dir}")
    return outputs


def status(settings: Settings) -> dict[str, Any]:
    if not settings.db_path.exists():
        return {"database": str(settings.db_path), "exists": False}
    con = connect(settings.db_path, read_only=True)
    try:
        counts: dict[str, int] = {}
        for relation, label in TABLE_COUNTS:
            if relation_exists(con, relation):
                counts[label] = int(fetch_one(con, f"SELECT COUNT(*) FROM {relation}") or 0)
        dq_info = None
        if relation_exists(con, "analytics.v_data_quality"):
            dq = con.execute(
                """
                SELECT COUNT(*) AS checks,
                       COUNT(*) FILTER (WHERE status = 'PASS') AS passed,
                       COUNT(*) FILTER (WHERE status <> 'PASS') AS failed
                FROM analytics.v_data_quality
                """
            ).fetchone()
            if dq is not None:
                dq_info = {"checks": int(dq[0]), "passed": int(dq[1]), "failed": int(dq[2])}
    finally:
        con.close()
    return {
        "database": str(settings.db_path),
        "exists": True,
        "counts": counts,
        "quality": dq_info,
    }


def build(
    settings: Settings,
    *,
    seed: int | None = None,
    reset: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Full run.  ``reset`` removes the existing DuckDB file first."""
    settings = apply_seed(settings, seed)
    settings.ensure_dirs()
    if reset:
        reset_database(settings)
    generate(settings, verbose=verbose)
    load(settings, verbose=verbose)
    transform(settings, verbose=verbose)
    results = run_quality(settings, verbose=verbose)
    export(settings, verbose=verbose)
    summary = quality_summary(settings)
    if verbose:
        print(
            f"[done] database={settings.db_path} "
            f"checks={summary['checks']} failed={summary['failed']}"
        )
    return {
        "settings": settings,
        "quality": summary,
        "quality_results": results,
    }
