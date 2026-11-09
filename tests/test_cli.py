"""Tests for the WealthOps command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wealthops.cli import build_parser, main
from wealthops.config import Settings


def test_build_parser_help(capsys) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "wealthops" in captured.out
    assert "status" in captured.out
    assert "quality" in captured.out
    assert "nlq" in captured.out


def test_cli_status(capsys, built: Settings) -> None:
    code = main(["--data-dir", str(built.data_dir), "status"])
    assert code == 0
    captured = capsys.readouterr()
    info = json.loads(captured.out)
    assert info["exists"] is True
    assert info["counts"]["clients"] == built.n_clients
    assert info["quality"]["passed"] >= 40
    assert info["quality"]["failed"] == 0


def test_cli_quality(capsys, built: Settings) -> None:
    code = main(["--data-dir", str(built.data_dir), "--quiet", "quality"])
    assert code == 0


def test_cli_nlq_without_show_sql(capsys, built: Settings) -> None:
    code = main([
        "--data-dir",
        str(built.data_dir),
        "nlq",
        "Show net new assets by month",
        "--limit",
        "5",
    ])
    assert code == 0
    captured = capsys.readouterr()
    # When --show-sql is not passed, "SQL:" header must not appear
    assert "SQL:" not in captured.out
    assert "net_new_assets_inr" in captured.out


def test_cli_nlq_with_show_sql(capsys, built: Settings) -> None:
    code = main([
        "--data-dir",
        str(built.data_dir),
        "nlq",
        "Show net new assets by month",
        "--limit",
        "5",
        "--show-sql",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "SQL:" in captured.out
    assert "analytics.kpi_monthly_flows" in captured.out
    assert "net_new_assets_inr" in captured.out


def test_cli_nlq_empty_question(capsys, built: Settings) -> None:
    code = main(["--data-dir", str(built.data_dir), "nlq", "   "])
    assert code == 2
    captured = capsys.readouterr()
    assert "Blocked:" in captured.err


def test_cli_nlq_unknown_question(capsys, built: Settings) -> None:
    code = main(["--data-dir", str(built.data_dir), "nlq", "Nonexistent metric 12345"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Blocked:" in captured.err


def test_cli_export(tmp_path: Path, built: Settings) -> None:
    export_dir = tmp_path / "cli_exports"
    code = main([
        "--data-dir",
        str(built.data_dir),
        "--export-dir",
        str(export_dir),
        "--quiet",
        "export",
    ])
    assert code == 0
    csvs = list(export_dir.glob("*.csv"))
    assert len(csvs) >= 8


def test_cli_custom_scenario_size_and_pipeline(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "custom_data"
    code_gen = main([
        "--data-dir",
        str(data_dir),
        "--clients",
        "50",
        "--advisors",
        "5",
        "--months",
        "6",
        "--quiet",
        "generate",
    ])
    assert code_gen == 0

    code_load = main(["--data-dir", str(data_dir), "--quiet", "load"])
    assert code_load == 0

    code_tf = main(["--data-dir", str(data_dir), "--quiet", "transform"])
    assert code_tf == 0

    code_stat = main(["--data-dir", str(data_dir), "status"])
    assert code_stat == 0
    captured = capsys.readouterr()
    info = json.loads(captured.out)
    assert info["exists"] is True
    assert info["counts"]["clients"] == 50
    assert info["counts"]["advisors"] == 5


def test_settings_from_env_all_variables(tmp_path: Path, monkeypatch) -> None:
    custom_data = tmp_path / "env_data"
    custom_export = tmp_path / "env_export"
    monkeypatch.setenv("WEALTHOPS_SEED", "99")
    monkeypatch.setenv("WEALTHOPS_CLIENTS", "250")
    monkeypatch.setenv("WEALTHOPS_ADVISORS", "12")
    monkeypatch.setenv("WEALTHOPS_CHANNELS", "4")
    monkeypatch.setenv("WEALTHOPS_MONTHS", "18")
    monkeypatch.setenv("WEALTHOPS_DATA_DIR", str(custom_data))
    monkeypatch.setenv("WEALTHOPS_EXPORT_DIR", str(custom_export))

    settings = Settings.from_env()
    assert settings.seed == 99
    assert settings.n_clients == 250
    assert settings.n_advisors == 12
    assert settings.n_channels == 4
    assert settings.months == 18
    assert settings.data_dir == custom_data
    assert settings.export_dir == custom_export


def test_cli_reset_and_explicit_db(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "reset_test"
    db_file = data_dir / "custom.duckdb"
    # Ensure directory exists and touch dummy database
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file.write_text("dummy", encoding="utf-8")
    assert db_file.exists()

    # Call reset via --db
    code = main(["--db", str(db_file), "reset"])
    assert code == 0
    # The default db_path in settings is data_dir / "wealthops.duckdb"
    # Testing reset command on standard db_path
    std_db = data_dir / "wealthops.duckdb"
    std_db.write_text("dummy", encoding="utf-8")
    assert std_db.exists()
    code_std = main(["--data-dir", str(data_dir), "reset"])
    assert code_std == 0
    assert not std_db.exists()
