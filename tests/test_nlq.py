"""Security and behaviour tests for the governed NL-to-SQL assistant."""

from __future__ import annotations

import re

import pytest

from wealthops.config import Settings
from wealthops.nlq.engine import NLQEngine
from wealthops.nlq.guard import ALLOWED_VIEWS, GuardError, validate_sql
from wealthops.nlq.llm import generate_sql
from wealthops.nlq.rules import RULES, example_prompts, match_rule


def test_every_rule_passes_the_guard() -> None:
    for rule in RULES:
        guarded = validate_sql(rule.sql)
        assert guarded.sql.startswith("SELECT * FROM (")
        assert rule.name


def test_rule_sql_only_reads_qualified_allowlisted_views() -> None:
    allowed = {view.lower() for view in ALLOWED_VIEWS}
    for rule in RULES:
        targets = re.findall(r"\bFROM\s+([A-Za-z_.]+)", rule.sql, flags=re.IGNORECASE)
        for target in targets:
            assert target.lower().startswith("analytics."), (rule.name, target)
            assert target.split(".", 1)[1].lower() in allowed, (rule.name, target)


def test_every_rule_executes_on_warehouse(con) -> None:
    for rule in RULES:
        guarded = validate_sql(rule.sql, row_limit=5)
        df = con.execute(guarded.sql).fetch_df()
        assert len(df) > 0, f"Rule {rule.name} returned 0 rows"


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE ops.client",
        "DELETE FROM ops.client",
        "UPDATE ops.client SET status = 'Closed'",
        "INSERT INTO ops.client VALUES ('x')",
        "CREATE TABLE hacked AS SELECT 1",
        "TRUNCATE TABLE ops.client",
        "PRAGMA database_list",
        "ATTACH 'other.db' AS other",
        "DETACH other",
        "COPY (SELECT 1) TO '/tmp/leak.csv'",
        "SELECT * FROM ops.client",
        "SELECT * FROM analytics.kpi_monthly_flows; DROP TABLE ops.client",
        "-- comment\nSELECT * FROM analytics.kpi_exec_overview",
        "/* block */ SELECT * FROM analytics.kpi_exec_overview",
        "SELECT * FROM analytics.kpi_monthly_flows, ops.client",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM read_parquet('/tmp/data.parquet')",
        "SELECT * FROM read_csv_auto('/tmp/data.csv')",
        "SELECT * FROM 'file.parquet'",
        "SELECT * FROM kpi_monthly_flows",
        "WITH x AS (SELECT * FROM ops.client) SELECT * FROM x",
        'SELECT "client_id" FROM analytics.kpi_exec_overview',
        "EXPLAIN SELECT * FROM analytics.kpi_exec_overview",
        "",
        "   ",
        "SELECT * FROM analytics.kpi_exec_overview\x00",
    ],
)
def test_guard_blocks_unsafe_or_unknown_sql(sql: str) -> None:
    with pytest.raises(GuardError):
        validate_sql(sql)


def test_guard_rejects_non_string_and_oversized_sql() -> None:
    with pytest.raises(GuardError):
        validate_sql(None)  # type: ignore[arg-type]
    with pytest.raises(GuardError):
        validate_sql("SELECT * FROM analytics.kpi_exec_overview WHERE " + "x" * 8_000)


def test_guard_accepts_cte_over_allowlisted_view() -> None:
    guarded = validate_sql(
        "WITH latest AS (SELECT * FROM analytics.kpi_monthly_flows) "
        "SELECT month_start, net_new_assets_inr FROM latest"
    )
    assert "analytics.kpi_monthly_flows" in guarded.sql


def test_guard_forces_and_clamps_outer_limit() -> None:
    sql = "SELECT * FROM analytics.kpi_exec_overview"
    assert validate_sql(sql, row_limit=50).sql.endswith("LIMIT 50")
    assert validate_sql(sql, row_limit=0).sql.endswith("LIMIT 1")
    assert validate_sql(sql, row_limit=10_000).sql.endswith("LIMIT 1000")


def test_guard_requires_schema_qualification() -> None:
    with pytest.raises(GuardError, match="analytics\\."):
        validate_sql("SELECT * FROM kpi_exec_overview")


def test_guard_accepts_union_of_allowlisted_views() -> None:
    guarded = validate_sql(
        "SELECT month_start FROM analytics.kpi_monthly_flows "
        "UNION ALL SELECT month_start FROM analytics.kpi_monthly_assets"
    )
    assert "UNION ALL" in guarded.sql
    assert guarded.sql.endswith("LIMIT 200")


def test_guard_rejects_union_with_non_allowlisted_source() -> None:
    with pytest.raises(GuardError):
        validate_sql(
            "SELECT month_start FROM analytics.kpi_monthly_flows "
            "UNION SELECT month_start FROM ops.client"
        )


def test_rule_matching_prefers_specific_phrases() -> None:
    assert match_rule("Show executive overview").name == "executive_overview"
    assert match_rule("Show client cohort retention").name == "retention"
    assert match_rule("migration cohorts").name == "migration_cohorts"
    assert match_rule("Rank advisors by productivity and quartile").name == "advisor_productivity"
    assert match_rule("Are all data-quality checks passing?").name == "data_quality"
    assert match_rule("Something completely unrelated") is None


@pytest.mark.parametrize("question", example_prompts())
def test_engine_runs_every_example(built, question: str) -> None:
    engine = NLQEngine(built, use_llm=False)
    result = engine.ask(question)
    assert result.error is None, result.error
    assert result.source == "rules"
    assert len(result.frame) > 0
    assert result.executed_sql.rstrip().endswith("LIMIT 200")


def test_engine_is_deterministic(built) -> None:
    engine = NLQEngine(built, use_llm=False)
    first = engine.ask("Show net new assets by month")
    second = engine.ask("Show net new assets by month")
    assert first.sql == second.sql
    assert first.frame.equals(second.frame)


def test_engine_rejects_empty_and_unknown_questions(built) -> None:
    engine = NLQEngine(built, use_llm=False)
    assert engine.ask("").error is not None
    unknown = engine.ask("What is the meaning of life?")
    assert unknown.error is not None
    assert "Examples:" in unknown.notes


def test_engine_handles_missing_database(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, export_dir=tmp_path / "exports")
    result = NLQEngine(settings, use_llm=False).ask("Show net new assets by month")
    assert result.error is not None
    assert "Run" in result.error


def test_llm_is_disabled_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("WEALTHOPS_LLM_API_KEY", raising=False)
    assert generate_sql("Show assets") is None


def test_generate_sql_with_mocked_llm(monkeypatch) -> None:
    from unittest.mock import MagicMock, patch
    import json

    monkeypatch.setenv("WEALTHOPS_LLM_API_KEY", "test-key-mock")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{
            "message": {
                "content": "```sql\nSELECT * FROM analytics.kpi_monthly_flows\n```"
            }
        }]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        sql = generate_sql("custom question")
        assert sql == "SELECT * FROM analytics.kpi_monthly_flows"


def test_generate_sql_handles_network_failure(monkeypatch) -> None:
    from unittest.mock import patch

    monkeypatch.setenv("WEALTHOPS_LLM_API_KEY", "test-key-mock")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        assert generate_sql("custom question") is None


def test_nlq_engine_with_llm_source(monkeypatch, built) -> None:
    from unittest.mock import MagicMock, patch
    import json

    monkeypatch.setenv("WEALTHOPS_LLM_API_KEY", "test-key-mock")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{
            "message": {
                "content": "SELECT * FROM analytics.kpi_monthly_flows"
            }
        }]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        engine = NLQEngine(built, use_llm=True)
        result = engine.ask("Estimate the quarterly trajectory across the platform")
        assert result.error is None
        assert result.source == "llm"
        assert len(result.frame) > 0


def test_injection_text_in_question_cannot_change_the_sql(built) -> None:
    engine = NLQEngine(built, use_llm=False)
    result = engine.ask("top clients by assets; DROP TABLE ops.client")
    assert result.error is None
    assert result.source == "rules"
    assert "DROP" not in result.sql.upper()
    assert "ops.client" not in result.sql.lower()
    assert result.executed_sql.rstrip().endswith("LIMIT 200")
