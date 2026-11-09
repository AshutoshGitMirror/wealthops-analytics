"""SQL safety guard for the optional natural-language assistant.

Defence in depth:
1. Only explicit allow-listed analytics views may be read.
2. Only one SELECT / WITH ... SELECT statement is allowed.
3. DDL, DML, PRAGMA, ATTACH, COPY, file/table functions and comments are denied.
4. Every query is wrapped in an outer LIMIT.
5. The engine executes on a read-only DuckDB connection.

The guard is intentionally conservative.  It is not a general SQL parser and
does not promise to accept every valid analytical query; it promises to reject
anything it cannot prove is a single read-only query over governed views.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_VIEWS: tuple[str, ...] = (
    "kpi_exec_overview",
    "kpi_monthly_flows",
    "kpi_flow_types",
    "kpi_monthly_assets",
    "kpi_channel_mix",
    "kpi_migration_to_advice",
    "kpi_migration_summary",
    "kpi_advice_funnel",
    "kpi_cohort_retention",
    "kpi_retention_summary",
    "kpi_advisor_productivity",
    "kpi_advisor_monthly",
    "kpi_top_advisors",
    "kpi_client_value",
    "kpi_top_clients",
    "kpi_client_segments",
    "kpi_engagement_monthly",
    "kpi_engagement_summary",
    "v_data_quality",
    "v_client_current_advisor",
    "v_warehouse_counts",
)

ALLOWED_QUALIFIED = frozenset(f"analytics.{view}" for view in ALLOWED_VIEWS)

DENIED_KEYWORDS = frozenset(
    """
    insert update delete merge upsert drop alter create replace truncate
    grant revoke attach detach copy export import pragma call execute set
    install load vacuum checkpoint begin commit rollback savepoint release
    analyze optimize use describe show summarize explain into recursive
    information_schema pg_catalog duckdb_ system
    """.split()
)

DENIED_FRAGMENTS = (
    "read_csv",
    "read_parquet",
    "read_json",
    "read_text",
    "read_blob",
    "read_xlsx",
    "parquet_scan",
    "csv_scan",
    "json_scan",
    "glob(",
    "sqlite_scan",
    "postgres_scan",
    "mysql_scan",
    "httpfs",
    "delta_scan",
    "iceberg_scan",
    "current_setting",
    "set_config",
)

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_CTE_RE = re.compile(rf"(?:\bwith\b|,)\s+({_IDENT})\s+as\s*\(", re.IGNORECASE)
_FROM_JOIN_RE = re.compile(
    rf"\b(?:from|join)\s+({_IDENT}(?:\s*\.\s*{_IDENT})?)",
    re.IGNORECASE,
)
_WORD_RE = re.compile(rf"\b({_IDENT})\b", re.IGNORECASE)


@dataclass(frozen=True)
class GuardedSQL:
    original: str
    sql: str

    @property
    def wrapped(self) -> str:
        return self.sql


class GuardError(ValueError):
    """Raised when generated SQL is not safe to execute."""


def _reject_comments(sql: str) -> None:
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise GuardError("SQL comments are not allowed.")


def _strip_trailing_semicolon(sql: str) -> str:
    text = sql.strip()
    if not text:
        raise GuardError("SQL is empty.")
    if text.endswith(";"):
        text = text[:-1].strip()
    # Any remaining semicolon would imply multiple statements.  A semicolon
    # inside a quoted string is unusual for analytics SQL and is rejected for
    # simplicity and safety.
    if ";" in text:
        raise GuardError("Only one SQL statement is allowed.")
    return text


def _cte_names(sql: str) -> set[str]:
    return {match.group(1).lower() for match in _CTE_RE.finditer(sql)}


def _from_targets(sql: str) -> list[str]:
    return [match.group(1).replace(" ", "").lower() for match in _FROM_JOIN_RE.finditer(sql)]


def _from_clause_has_comma(sql: str) -> bool:
    """Detect comma joins at parenthesis depth 0 inside a FROM clause."""
    lower = sql.lower()
    i = 0
    n = len(lower)
    while True:
        idx = lower.find("from", i)
        if idx == -1:
            return False
        # Must be a word boundary.
        before = lower[idx - 1] if idx > 0 else " "
        after = lower[idx + 4] if idx + 4 < n else " "
        if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
            depth = 0
            j = idx + 4
            in_single = False
            while j < n:
                ch = lower[j]
                if in_single:
                    if ch == "'":
                        in_single = False
                    j += 1
                    continue
                if ch == "'":
                    in_single = True
                    j += 1
                    continue
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    if depth == 0:
                        break
                    depth -= 1
                elif depth == 0 and ch == ",":
                    return True
                elif depth == 0:
                    # Stop at the next top-level clause.
                    for word in ("where", "group", "order", "having", "limit", "union", "qualify"):
                        if lower.startswith(word, j) and (j == 0 or not lower[j - 1].isalnum()):
                            end = j + len(word)
                            if end >= n or not (lower[end].isalnum() or lower[end] == "_"):
                                return False
                j += 1
        i = idx + 4
    return False


def validate_sql(
    sql: str,
    *,
    row_limit: int = 200,
    allowed_views: tuple[str, ...] = ALLOWED_VIEWS,
) -> GuardedSQL:
    """Validate *sql* and return it wrapped in a forced outer LIMIT."""
    if not isinstance(sql, str):
        raise GuardError("SQL must be a string.")
    if len(sql) > 8_000:
        raise GuardError("SQL is too long.")
    if "\x00" in sql:
        raise GuardError("SQL contains a null byte.")
    _reject_comments(sql)
    if '"' in sql:
        raise GuardError("Double-quoted identifiers are not allowed.")
    text = _strip_trailing_semicolon(sql)

    if not re.match(r"^\s*(select|with)\b", text, re.IGNORECASE):
        raise GuardError("Only SELECT or WITH ... SELECT queries are allowed.")

    words = {match.group(1).lower() for match in _WORD_RE.finditer(text)}
    denied = sorted(words & DENIED_KEYWORDS)
    if denied:
        raise GuardError(f"Denied SQL keyword(s): {', '.join(denied)}.")
    lowered = text.lower()
    for fragment in DENIED_FRAGMENTS:
        if fragment in lowered:
            raise GuardError(f"Denied SQL function/fragment: {fragment}.")
    if re.search(r"\b(?:from|join)\s+'", text, re.IGNORECASE):
        raise GuardError("File paths and string literals are not valid FROM/JOIN targets.")

    if _from_clause_has_comma(text):
        raise GuardError("Comma joins are not allowed; use explicit JOINs.")

    allowed = {view.lower() for view in allowed_views}
    allowed_qualified = {f"analytics.{view}" for view in allowed}
    ctes = _cte_names(text)
    for target in _from_targets(text):
        if target in ctes:
            continue
        if target in allowed_qualified:
            continue
        if "." not in target and target in allowed:
            # Unqualified allow-listed views are rejected so the executed SQL
            # never depends on DuckDB's search_path.
            raise GuardError(
                f"Qualify allow-listed views as analytics.{target}."
            )
        raise GuardError(
            f"Table/view '{target}' is not in the allow-list. "
            f"Allowed views: {', '.join(sorted(allowed))}."
        )

    limit = max(1, min(int(row_limit), 1_000))
    wrapped = f"SELECT * FROM (\n{text}\n) AS _guarded_query\nLIMIT {limit}"
    return GuardedSQL(original=sql.strip(), sql=wrapped)


def describe_allowlist() -> str:
    return "\n".join(f"- analytics.{view}" for view in ALLOWED_VIEWS)
