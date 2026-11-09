"""Optional LLM adapter for the governed assistant.

This is intentionally a thin interface, not a required dependency.  The project
works fully offline with the deterministic rules engine in ``rules.py``.  If an
OpenAI-compatible endpoint is configured, the model is asked for one SELECT over
the allow-listed views; the result still passes through ``guard.validate_sql``
and executes on a read-only connection.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .rules import allowlist_text

SYSTEM_PROMPT = """You are a careful analytics SQL assistant for a synthetic wealth-management demo.
Return exactly one SQL statement and nothing else.
Rules:
- Use only the allow-listed views below. Qualify every view as analytics.<name>.
- SELECT or WITH ... SELECT only. No comments, DDL, DML, PRAGMA, ATTACH, COPY or table functions.
- Never invent columns. Use the documented view columns.
- Keep the result small; the application adds an outer LIMIT.
"""


def _schema_hint() -> str:
    return """Key views and columns:
analytics.kpi_exec_overview: as_of_month, total_assets_inr, fee_based_share_pct, active_clients, nna_ltm_inr, migration_rate_pct, retention_12m_pct
analytics.kpi_monthly_flows: month_start, inflows_inr, outflows_inr, net_new_assets_inr, nna_mom_pct, nna_ltm_inr
analytics.kpi_monthly_assets: month_start, total_assets_inr, fee_based_assets_inr, fee_based_share_pct, estimated_fee_revenue_inr
analytics.kpi_channel_mix: month_start, channel_name, clients, total_assets_inr, assets_share_pct, nna_inr, nna_ltm_inr
analytics.kpi_migration_summary: channel_name, eligible_clients, migrated_clients, migration_rate_pct
analytics.kpi_migration_to_advice: cohort_month, eligible_clients, migrated_clients, migration_rate_pct
analytics.kpi_cohort_retention: cohort_month, months_since_onboarding, cohort_size, retained_clients, retention_rate_pct, is_observed
analytics.kpi_advisor_productivity: advisor_name, region, clients, total_assets_inr, nna_ltm_inr, nna_rank, productivity_quartile
analytics.kpi_top_clients: client_id, segment, channel_name, advisor_name, total_assets_inr, asset_rank
analytics.kpi_client_segments: segment, clients, total_assets_inr, assets_share_pct, fee_based_share_pct
analytics.kpi_engagement_summary: month_start, events, engaged_clients, advice_meetings, plans_created
analytics.kpi_advice_funnel: channel_name, clients, engaged_clients, planned_clients, fee_based_clients
analytics.v_data_quality: check_name, category, severity, status, observed, expected, details
"""


def llm_enabled() -> bool:
    return bool(os.getenv("WEALTHOPS_LLM_API_KEY"))


def generate_sql(question: str, timeout: int = 20) -> str | None:
    """Return SQL from an optional OpenAI-compatible endpoint, or None.

    Any network/configuration/parse error returns None so the caller can fall
    back to the deterministic rules.  No key is ever logged.
    """
    api_key = os.getenv("WEALTHOPS_LLM_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("WEALTHOPS_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("WEALTHOPS_LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Allow-listed views:\n{allowlist_text()}\n\n{_schema_hint()}\n\nQuestion: {question}\nSQL:",
            },
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        # Strip a markdown code fence if the model added one.
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            content = content.rsplit("```", 1)[0].strip()
        return content or None
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError, TimeoutError):
        return None
