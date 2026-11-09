"""Deterministic rule-based natural-language to SQL fallback.

The rules are deliberately narrow: the assistant is a demo of governed access,
not a general text-to-SQL product.  Every statement targets a curated KPI view
and is still validated by :mod:`wealthops.nlq.guard`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .guard import ALLOWED_VIEWS


@dataclass(frozen=True)
class Rule:
    name: str
    keywords: tuple[str, ...]
    sql: str
    description: str


RULES: tuple[Rule, ...] = (
    Rule(
        name="data_quality",
        keywords=("data quality", "dq", "checks", "validation", "test result"),
        sql="SELECT * FROM analytics.v_data_quality ORDER BY category, check_name",
        description="All data-quality check results, newest run only.",
    ),
    Rule(
        name="executive_overview",
        keywords=("executive overview", "overview", "headline", "kpi snapshot"),
        sql="SELECT * FROM analytics.kpi_exec_overview",
        description="One-row executive snapshot for the latest month.",
    ),
    Rule(
        name="monthly_flows",
        keywords=("net new", "nna", "flow", "inflow", "outflow", "assets by month", "monthly trend"),
        sql=(
            "SELECT month_start, inflows_inr, outflows_inr, net_new_assets_inr, "
            "nna_mom_pct, running_nna_inr, nna_ltm_inr "
            "FROM analytics.kpi_monthly_flows ORDER BY month_start"
        ),
        description="Monthly external inflows, outflows and net new assets.",
    ),
    Rule(
        name="flow_types",
        keywords=("flow type", "transaction type", "deposit", "withdrawal", "transfer"),
        sql=(
            "SELECT month_start, flow_type, direction, flow_count, client_count, "
            "gross_amount_inr, nna_inr FROM analytics.kpi_flow_types "
            "ORDER BY month_start, flow_type"
        ),
        description="Flow-type detail by month and direction.",
    ),
    Rule(
        name="fee_based",
        keywords=("fee-based", "fee based", "fee revenue", "advisory fee", "managed assets"),
        sql=(
            "SELECT month_start, total_assets_inr, fee_based_assets_inr, "
            "fee_based_share_pct, estimated_fee_revenue_inr, fee_based_share_mom_pp "
            "FROM analytics.kpi_monthly_assets ORDER BY month_start"
        ),
        description="Fee-based assets, share and synthetic fee revenue by month.",
    ),
    Rule(
        name="channel_mix",
        keywords=("channel", "digital", "branch", "advisor-led"),
        sql=(
            "SELECT * FROM analytics.kpi_channel_mix "
            "WHERE month_start = (SELECT MAX(month_start) FROM analytics.kpi_channel_mix) "
            "ORDER BY total_assets_inr DESC"
        ),
        description="Latest-month client and asset mix by acquisition channel.",
    ),
    Rule(
        name="advice_funnel",
        keywords=("funnel", "engaged", "planning rate"),
        sql="SELECT * FROM analytics.kpi_advice_funnel ORDER BY clients DESC",
        description="Client engagement, planning and fee-based funnel by channel.",
    ),
    Rule(
        name="migration",
        keywords=("migration", "migrate", "advice rate", "conversion", "plan rate"),
        sql="SELECT * FROM analytics.kpi_migration_summary",
        description="Digital-client migration-to-advice summary.",
    ),
    Rule(
        name="migration_cohorts",
        keywords=("migration cohort", "advice cohort"),
        sql=(
            "SELECT * FROM analytics.kpi_migration_to_advice "
            "ORDER BY cohort_month DESC"
        ),
        description="Migration-to-advice by onboarding cohort.",
    ),
    Rule(
        name="retention",
        keywords=("retention", "cohort", "churn", "retain"),
        sql=(
            "SELECT * FROM analytics.kpi_cohort_retention "
            "WHERE is_observed ORDER BY cohort_month, months_since_onboarding"
        ),
        description="Observed client asset-retention by onboarding cohort.",
    ),
    Rule(
        name="advisor_productivity",
        keywords=("advisor productivity", "advisor book", "top advisor", "quartile", "productivity"),
        sql=(
            "SELECT advisor_name, region, clients, total_assets_inr, nna_ltm_inr, "
            "nna_rank, productivity_quartile, assets_per_client_inr, fee_based_share_pct "
            "FROM analytics.kpi_advisor_productivity ORDER BY nna_rank"
        ),
        description="Advisor book size, NNA, rank and productivity quartile.",
    ),
    Rule(
        name="top_advisors",
        keywords=("top 10 advisor", "best advisor", "rank advisor"),
        sql="SELECT * FROM analytics.kpi_top_advisors ORDER BY nna_rank",
        description="Top-10 advisors by trailing-12-month NNA.",
    ),
    Rule(
        name="top_clients",
        keywords=("top client", "largest client", "high value", "hni client"),
        sql=(
            "SELECT client_id, client_name, segment, channel_name, advisor_name, "
            "total_assets_inr, nna_ltm_inr, asset_rank, asset_decile "
            "FROM analytics.kpi_top_clients ORDER BY asset_rank"
        ),
        description="Top-25 clients by latest assets.",
    ),
    Rule(
        name="segments",
        keywords=("segment", "mass affluent", "ultra hni", "client mix"),
        sql="SELECT * FROM analytics.kpi_client_segments ORDER BY total_assets_inr DESC",
        description="Latest-month client and asset mix by wealth segment.",
    ),
    Rule(
        name="engagement",
        keywords=("engagement", "meeting", "plan created", "activity", "planning event"),
        sql=(
            "SELECT * FROM analytics.kpi_engagement_summary ORDER BY month_start"
        ),
        description="Monthly engagement, advice meetings and planning activity.",
    ),
)


def match_rule(question: str) -> Rule | None:
    """Return the rule with the strongest keyword evidence in the question.

    Longer phrases win over shorter ones so that "migration cohorts" selects
    the cohort detail rule rather than the headline migration rule.
    """
    q = " ".join(question.lower().split())
    best: Rule | None = None
    best_score = 0
    for rule in RULES:
        score = sum(len(keyword) for keyword in rule.keywords if keyword in q)
        if score > best_score:
            best, best_score = rule, score
    return best


def example_prompts() -> list[str]:
    return [
        "Show net new assets by month",
        "What is the fee-based asset share trend?",
        "Compare the latest channel mix",
        "What is the digital migration-to-advice rate?",
        "Show client cohort retention",
        "Rank advisors by productivity and quartile",
        "Who are the top clients by assets?",
        "Are all data-quality checks passing?",
    ]


def allowlist_text() -> str:
    return "\n".join(f"- analytics.{view}" for view in ALLOWED_VIEWS)
