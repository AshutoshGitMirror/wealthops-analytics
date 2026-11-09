"""Governed natural-language query engine.

The deterministic rules engine is the default.  An optional LLM adapter can be
enabled with environment variables; its SQL is validated by the same guard and
executed on a read-only connection.  The assistant never sees raw operational
tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..config import Settings
from ..db import connect
from .guard import ALLOWED_VIEWS, GuardError, validate_sql
from .llm import generate_sql, llm_enabled
from .rules import Rule, example_prompts, match_rule


@dataclass
class NLQResult:
    question: str
    sql: str = ""
    executed_sql: str = ""
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    source: str = "rules"
    error: str | None = None
    notes: str = ""


class NLQEngine:
    def __init__(
        self,
        settings: Settings,
        *,
        row_limit: int = 200,
        use_llm: bool | None = None,
    ) -> None:
        self.settings = settings
        self.row_limit = max(1, min(int(row_limit), 1_000))
        self.use_llm = llm_enabled() if use_llm is None else use_llm

    @property
    def allowlist(self) -> tuple[str, ...]:
        return ALLOWED_VIEWS

    def _choose_sql(self, question: str) -> tuple[str, str, str]:
        rule: Rule | None = match_rule(question)
        if rule is not None:
            return rule.sql, "rules", rule.description
        if self.use_llm:
            generated = generate_sql(question)
            if generated:
                return generated, "llm", "SQL produced by the optional LLM adapter and passed through the guard."
        return (
            "",
            "none",
            "No matching governed question. Try one of the example prompts.",
        )

    def ask(self, question: str) -> NLQResult:
        if not question or not question.strip():
            return NLQResult(question=question, error="Enter a question.")
        if not self.settings.db_path.exists():
            return NLQResult(
                question=question,
                error=f"Database not found at {self.settings.db_path}. Run `make demo` or `wealthops build` first.",
            )

        sql, source, notes = self._choose_sql(question)
        if not sql:
            return NLQResult(
                question=question,
                source=source,
                error=notes,
                notes="Examples: " + " | ".join(example_prompts()),
            )

        try:
            guarded = validate_sql(sql, row_limit=self.row_limit)
        except GuardError as exc:
            return NLQResult(question=question, sql=sql, source=source, error=str(exc))

        try:
            con = connect(self.settings.db_path, read_only=True)
            try:
                frame = con.execute(guarded.sql).fetch_df()
            finally:
                con.close()
        except Exception as exc:  # pragma: no cover - defensive runtime path
            return NLQResult(
                question=question,
                sql=sql,
                executed_sql=guarded.sql,
                source=source,
                error=f"Query failed: {exc}",
            )

        return NLQResult(
            question=question,
            sql=sql,
            executed_sql=guarded.sql,
            frame=frame.head(self.row_limit),
            source=source,
            notes=notes,
        )

    @staticmethod
    def examples() -> list[str]:
        return example_prompts()
