"""Shared pytest fixtures.

A single small warehouse is built once per test session.  The fixture uses the
same code path as ``make demo`` but with 1,200 clients so the suite stays fast
on a two-core laptop.  All expected counts still come from the generated
manifest; nothing in the quality checks assumes the production-sized 5,000.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from wealthops.config import Settings  # noqa: E402
from wealthops.db import connect, fetch_df  # noqa: E402
from wealthops.pipeline import build  # noqa: E402


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Build the test warehouse once and fail early if any check is red."""
    data_dir = tmp_path_factory.mktemp("wealthops-test")
    settings = Settings(
        n_clients=1_200,
        data_dir=data_dir,
        export_dir=data_dir / "exports",
    )
    summary = build(settings, reset=True, verbose=False)
    assert summary["quality"]["failed"] == 0, summary["quality_results"].query(
        "status != 'PASS'"
    )
    return settings


@pytest.fixture(scope="session")
def con(built: Settings) -> Iterator:
    connection = connect(built.db_path, read_only=True)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture(scope="session")
def query(con):
    def run(sql: str, params: list | None = None):
        return fetch_df(con, sql, params)

    return run


@pytest.fixture(scope="session")
def manifest(built: Settings) -> dict:
    import json

    path = built.raw_dir / "_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))
