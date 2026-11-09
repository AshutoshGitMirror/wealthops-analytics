"""Read-only data access for the Streamlit dashboard.

Every function opens a short-lived read-only DuckDB connection.  The dashboard
never writes to the warehouse and never sees raw operational tables directly;
it reads the governed KPI views.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from ..config import Settings
from ..db import connect, fetch_df


def _read(db_path: str | Path, sql: str, params: list | None = None) -> pd.DataFrame:
    con = connect(db_path, read_only=True)
    try:
        return fetch_df(con, sql, params)
    finally:
        con.close()


def load_months(db_path: str | Path) -> list[date]:
    frame = _read(
        db_path,
        "SELECT DISTINCT month_start FROM analytics.kpi_monthly_assets ORDER BY month_start",
    )
    return [value.date() if hasattr(value, "date") else value for value in frame["month_start"]]


def load_exec(db_path: str | Path) -> pd.DataFrame:
    return _read(db_path, "SELECT * FROM analytics.kpi_exec_overview")


def load_manifest(data_dir: str | Path) -> dict:
    path = Path(data_dir) / "raw" / "_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_counts(db_path: str | Path) -> pd.DataFrame:
    return _read(db_path, "SELECT metric, value FROM analytics.v_warehouse_counts")


def load_monthly_flows(db_path: str | Path, start: date, end: date) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_monthly_flows
        WHERE month_start BETWEEN ? AND ?
        ORDER BY month_start
        """,
        [start, end],
    )


def load_monthly_assets(db_path: str | Path, start: date, end: date) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_monthly_assets
        WHERE month_start BETWEEN ? AND ?
        ORDER BY month_start
        """,
        [start, end],
    )


def load_channel_mix(
    db_path: str | Path,
    start: date,
    end: date,
    channels: list[str] | None = None,
) -> pd.DataFrame:
    sql = """
        SELECT * FROM analytics.kpi_channel_mix
        WHERE month_start BETWEEN ? AND ?
    """
    params: list = [start, end]
    if channels:
        sql += f" AND channel_name IN ({','.join('?' for _ in channels)})"
        params.extend(channels)
    sql += " ORDER BY month_start, channel_name"
    return _read(db_path, sql, params)


def load_flow_types(db_path: str | Path, start: date, end: date) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_flow_types
        WHERE month_start BETWEEN ? AND ?
        ORDER BY month_start, flow_type
        """,
        [start, end],
    )


def load_funnel(db_path: str | Path) -> pd.DataFrame:
    return _read(db_path, "SELECT * FROM analytics.kpi_advice_funnel ORDER BY clients DESC")


def load_migration_summary(db_path: str | Path) -> pd.DataFrame:
    return _read(db_path, "SELECT * FROM analytics.kpi_migration_summary")


def load_migration_cohorts(db_path: str | Path) -> pd.DataFrame:
    return _read(
        db_path,
        "SELECT * FROM analytics.kpi_migration_to_advice ORDER BY cohort_month",
    )


def load_retention(
    db_path: str | Path, start: date, end: date
) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_cohort_retention
        WHERE is_observed AND cohort_month BETWEEN ? AND ?
        ORDER BY cohort_month, months_since_onboarding
        """,
        [start, end],
    )


def load_advisor_productivity(db_path: str | Path) -> pd.DataFrame:
    return _read(
        db_path,
        "SELECT * FROM analytics.kpi_advisor_productivity ORDER BY nna_rank",
    )


def load_advisor_monthly(db_path: str | Path, advisor_name: str) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_advisor_monthly
        WHERE advisor_name = ?
        ORDER BY month_start
        """,
        [advisor_name],
    )


def load_top_advisors(db_path: str | Path, limit: int = 10) -> pd.DataFrame:
    return _read(
        db_path,
        "SELECT * FROM analytics.kpi_top_advisors ORDER BY nna_rank LIMIT ?",
        [int(limit)],
    )


def load_client_segments(db_path: str | Path) -> pd.DataFrame:
    return _read(db_path, "SELECT * FROM analytics.kpi_client_segments ORDER BY total_assets_inr DESC")


def load_top_clients(db_path: str | Path, limit: int = 25) -> pd.DataFrame:
    return _read(
        db_path,
        "SELECT * FROM analytics.kpi_top_clients ORDER BY asset_rank LIMIT ?",
        [int(limit)],
    )


def load_engagement(db_path: str | Path, start: date, end: date) -> pd.DataFrame:
    return _read(
        db_path,
        """
        SELECT * FROM analytics.kpi_engagement_summary
        WHERE month_start BETWEEN ? AND ?
        ORDER BY month_start
        """,
        [start, end],
    )


def load_quality(db_path: str | Path) -> pd.DataFrame:
    return _read(
        db_path,
        "SELECT * FROM analytics.v_data_quality ORDER BY category, check_name",
    )


def load_channel_options(db_path: str | Path) -> list[str]:
    frame = _read(
        db_path,
        "SELECT DISTINCT channel_name FROM analytics.dim_channel ORDER BY 1",
    )
    return frame["channel_name"].tolist()


def load_segment_options(db_path: str | Path) -> list[str]:
    frame = _read(
        db_path,
        "SELECT DISTINCT segment FROM analytics.dim_client ORDER BY 1",
    )
    return frame["segment"].tolist()


def load_advisor_options(db_path: str | Path) -> list[str]:
    frame = _read(
        db_path,
        """
        SELECT advisor_name FROM analytics.dim_advisor
        WHERE advisor_key > 0 ORDER BY advisor_name
        """,
    )
    return frame["advisor_name"].tolist()
