"""DuckDB connection helpers and small SQL runner.

The project keeps SQL in ``sql/`` as first-class artefacts.  This module is
deliberately thin: connect, split a script into statements, execute it and
return DataFrames.  No business logic lives here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd


def connect(db_path: str | Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with modest, laptop-friendly limits."""
    path = str(db_path)
    con = duckdb.connect(path, read_only=read_only)
    con.execute("SET threads = 2")
    if not read_only:
        con.execute("SET memory_limit = '2GB'")
    return con


def split_sql(script: str) -> list[str]:
    """Split a SQL script on semicolons outside quotes and comments.

    DuckDB's Python API runs one statement per ``execute`` call.  Keeping a
    tiny splitter makes multi-statement ``.sql`` files usable without adding a
    parser dependency.  The SQL in this repository is simple enough that a
    quote/comment-aware scanner is sufficient.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    n = len(script)

    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue
        if in_single:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":  # escaped quote
                    buf.append(nxt)
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            buf.extend([ch, nxt])
            i += 2
            in_line_comment = True
            continue

        if ch == "/" and nxt == "*":
            buf.extend([ch, nxt])
            i += 2
            in_block_comment = True
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def execute_script(
    con: duckdb.DuckDBPyConnection,
    script: str,
    *,
    source: str = "<sql>",
) -> int:
    """Execute every statement in *script*.  Returns statement count."""
    statements = split_sql(script)
    for idx, statement in enumerate(statements, start=1):
        try:
            con.execute(statement)
        except Exception as exc:  # pragma: no cover - message is the point
            raise RuntimeError(
                f"SQL failed in {source} at statement {idx}: {exc}\n"
                f"Statement:\n{statement[:1200]}"
            ) from exc
    return len(statements)


def render_sql(script: str, *, raw_dir: Path | None = None) -> str:
    """Substitute the one placeholder used by the load scripts."""
    if raw_dir is None:
        return script
    # DuckDB string literals use single quotes; paths are controlled locally.
    escaped = str(raw_dir).replace("'", "''")
    return script.replace("__RAW_DIR__", escaped)


def run_sql_file(
    con: duckdb.DuckDBPyConnection,
    path: str | Path,
    *,
    raw_dir: Path | None = None,
) -> int:
    p = Path(path)
    script = render_sql(p.read_text(encoding="utf-8"), raw_dir=raw_dir)
    return execute_script(con, script, source=str(p))


def run_sql_dir(
    con: duckdb.DuckDBPyConnection,
    directory: str | Path,
    *,
    raw_dir: Path | None = None,
    pattern: str = "*.sql",
) -> list[str]:
    """Run every matching SQL file in lexical order.  Returns file names."""
    files = sorted(Path(directory).glob(pattern))
    for path in files:
        run_sql_file(con, path, raw_dir=raw_dir)
    return [p.name for p in files]


def fetch_df(con: duckdb.DuckDBPyConnection, sql: str, params: Iterable | None = None) -> pd.DataFrame:
    """Run a query and return a DataFrame (parameterised when supplied)."""
    if params is None:
        return con.execute(sql).fetch_df()
    return con.execute(sql, list(params)).fetch_df()


def fetch_one(con: duckdb.DuckDBPyConnection, sql: str, params: Iterable | None = None):
    row = con.execute(sql, list(params or [])).fetchone()
    return row[0] if row else None


def relation_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """Return True for a table or view, schema-qualified or not."""
    schema, _, rel = name.rpartition(".")
    if not schema:
        schema, rel = "main", name
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, rel],
    ).fetchone()
    return bool(row and row[0])


def drop_database_files(db_path: str | Path) -> None:
    """Remove a local DuckDB database and its WAL file, if present."""
    path = Path(db_path)
    for candidate in (path, Path(str(path) + ".wal")):
        if candidate.exists():
            candidate.unlink()


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name: str) -> str:
    """Quote a simple identifier for dynamically built SQL."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return f'"{name}"'
