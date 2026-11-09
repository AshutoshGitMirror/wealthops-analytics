"""Streamlit dashboard for the WealthOps synthetic analytics workbench."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from wealthops.config import Settings  # noqa: E402
from wealthops.dashboard import data as d  # noqa: E402
from wealthops.nlq.engine import NLQEngine  # noqa: E402

NAVY = "#0B1F33"
TEAL = "#0F766E"
TEAL_LIGHT = "#5EEAD4"
GOLD = "#C9A227"
SLATE = "#64748B"
RED = "#B91C1C"
GREEN = "#15803D"
PALETTE = [TEAL, GOLD, "#2563EB", "#9333EA", "#DB2777", "#EA580C"]

DB_PATH = Path(os.getenv("WEALTHOPS_DB_PATH", ROOT / "data" / "wealthops.duckdb"))
DATA_DIR = DB_PATH.parent

st.set_page_config(
    page_title="WealthOps Analytics",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
.stApp { background: linear-gradient(180deg, #F7F9FC 0%, #EEF3F7 100%); }
section[data-testid="stSidebar"] { background: #0B1F33; }
section[data-testid="stSidebar"] * { color: #E2E8F0; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMultiSelect label { color: #CBD5E1 !important; }
section[data-testid="stSidebar"] hr { border-color: #1E3A5F; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px; }
h1, h2, h3 { color: #0B1F33; letter-spacing: -0.02em; }
.wo-header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom: 12px; }
.wo-title { font-size: 1.9rem; font-weight: 700; color:#0B1F33; line-height:1.1; }
.wo-badge { background:#FEF3C7; color:#92400E; border:1px solid #FCD34D; padding:6px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; white-space:nowrap; }
.wo-card { background:white; border:1px solid #E2E8F0; border-radius:14px; padding:14px 16px; box-shadow:0 2px 6px rgba(15,23,42,0.04); }
.wo-card .label { color:#64748B; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em; font-weight:600; }
.wo-card .value { color:#0B1F33; font-size:1.65rem; font-weight:700; margin-top:4px; }
.wo-card .sub { color:#64748B; font-size:0.78rem; margin-top:4px; }
.wo-section { margin: 1.2rem 0 0.4rem 0; font-size:1.05rem; font-weight:700; color:#0B1F33; }
.wo-caption { color:#64748B; font-size:0.82rem; }
.wo-pill { display:inline-block; padding:3px 8px; border-radius:999px; font-size:0.72rem; font-weight:600; }
.wo-pass { background:#DCFCE7; color:#166534; }
.wo-fail { background:#FEE2E2; color:#991B1B; }
.wo-source { background:#E0F2FE; color:#075985; }
div[data-testid="stMetric"] { background:white; border:1px solid #E2E8F0; border-radius:14px; padding:12px 14px; }
div[data-testid="stDataFrame"] { border:1px solid #E2E8F0; border-radius:12px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def cr(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"₹{value / 1e7:,.1f} Cr"


def pct(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}%"


def num(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.0f}"


def card(label: str, value: str, sub: str = "") -> None:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="wo-card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def style_fig(fig: go.Figure, *, height: int = 330) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Inter, sans-serif", color=NAVY, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0")
    fig.update_yaxes(gridcolor="#E2E8F0", zerolinecolor="#CBD5E1")
    return fig


@st.cache_data(ttl=180, show_spinner=False)
def q_months(db: str) -> list[date]:
    return d.load_months(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_exec(db: str) -> pd.DataFrame:
    return d.load_exec(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_flows(db: str, start: date, end: date) -> pd.DataFrame:
    return d.load_monthly_flows(db, start, end)


@st.cache_data(ttl=180, show_spinner=False)
def q_assets(db: str, start: date, end: date) -> pd.DataFrame:
    return d.load_monthly_assets(db, start, end)


@st.cache_data(ttl=180, show_spinner=False)
def q_channel(db: str, start: date, end: date, channels: tuple[str, ...]) -> pd.DataFrame:
    return d.load_channel_mix(db, start, end, list(channels) or None)


@st.cache_data(ttl=180, show_spinner=False)
def q_flow_types(db: str, start: date, end: date) -> pd.DataFrame:
    return d.load_flow_types(db, start, end)


@st.cache_data(ttl=180, show_spinner=False)
def q_funnel(db: str) -> pd.DataFrame:
    return d.load_funnel(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_migration(db: str) -> pd.DataFrame:
    return d.load_migration_summary(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_migration_cohorts(db: str) -> pd.DataFrame:
    return d.load_migration_cohorts(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_retention(db: str, start: date, end: date) -> pd.DataFrame:
    return d.load_retention(db, start, end)


@st.cache_data(ttl=180, show_spinner=False)
def q_advisors(db: str) -> pd.DataFrame:
    return d.load_advisor_productivity(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_advisor_monthly(db: str, advisor: str) -> pd.DataFrame:
    return d.load_advisor_monthly(db, advisor)


@st.cache_data(ttl=180, show_spinner=False)
def q_segments(db: str) -> pd.DataFrame:
    return d.load_client_segments(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_top_clients(db: str) -> pd.DataFrame:
    return d.load_top_clients(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_engagement(db: str, start: date, end: date) -> pd.DataFrame:
    return d.load_engagement(db, start, end)


@st.cache_data(ttl=180, show_spinner=False)
def q_quality(db: str) -> pd.DataFrame:
    return d.load_quality(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_counts(db: str) -> pd.DataFrame:
    return d.load_counts(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_channels(db: str) -> list[str]:
    return d.load_channel_options(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_segment_options(db: str) -> list[str]:
    return d.load_segment_options(db)


@st.cache_data(ttl=180, show_spinner=False)
def q_advisor_options(db: str) -> list[str]:
    return d.load_advisor_options(db)


# ---------------------------------------------------------------------------
# Header and sidebar
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="wo-header">
      <div class="wo-title">WealthOps Analytics</div>
      <div class="wo-badge">SYNTHETIC DATA · NOT A REAL FIRM · NO CLIENT DATA</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not DB_PATH.exists():
    st.warning(
        "No warehouse found. Run `make demo` (or `wealthops build --reset`) "
        "and then refresh this page."
    )
    st.stop()

months = q_months(str(DB_PATH))
if not months:
    st.warning("The warehouse has no monthly data. Rebuild with `make demo`.")
    st.stop()

with st.sidebar:
    st.markdown("### ◈ WealthOps")
    st.markdown("---")
    nav = st.radio(
        "Workspace",
        [
            "Executive overview",
            "Flows & channels",
            "Advisor book",
            "Client cohorts",
            "Data quality",
            "Ask the data",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**Filters**")
    start_month = st.selectbox(
        "From month",
        options=months,
        index=0,
        format_func=lambda x: x.strftime("%b %Y"),
    )
    end_month = st.selectbox(
        "To month",
        options=months,
        index=len(months) - 1,
        format_func=lambda x: x.strftime("%b %Y"),
    )
    if start_month > end_month:
        start_month, end_month = end_month, start_month
    channel_opts = q_channels(str(DB_PATH))
    selected_channels = st.multiselect("Channels", channel_opts, default=channel_opts)
    segment_opts = q_segment_options(str(DB_PATH))
    selected_segments = st.multiselect("Segments", segment_opts, default=segment_opts)
    if st.button("Refresh cached data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Executive overview
# ---------------------------------------------------------------------------
if nav == "Executive overview":
    exec_row = q_exec(str(DB_PATH)).iloc[0]
    flows = q_flows(str(DB_PATH), start_month, end_month)
    assets = q_assets(str(DB_PATH), start_month, end_month)
    channel = q_channel(str(DB_PATH), start_month, end_month, tuple(selected_channels))
    advisors = q_advisors(str(DB_PATH))

    c1, c2, c3 = st.columns(3)
    with c1:
        card("Assets under analytics", cr(exec_row["total_assets_inr"]), f"as of {exec_row['as_of_month_end']:%b %Y}")
    with c2:
        card("Net new assets · LTM", cr(exec_row["nna_ltm_inr"]), f"latest month {cr(exec_row['latest_month_nna_inr'])}")
    with c3:
        card("Fee-based asset share", pct(exec_row["fee_based_share_pct"]), f"{cr(exec_row['fee_based_assets_inr'])} fee-based")

    c4, c5, c6 = st.columns(3)
    with c4:
        card("Active clients", num(exec_row["active_clients"]), f"{num(exec_row['active_accounts'])} funded accounts")
    with c5:
        card("12-month cohort retention", pct(exec_row["retention_12m_pct"]))
    with c6:
        card("Digital migration to advice", pct(exec_row["migration_rate_pct"]))

    st.markdown('<div class="wo-section">Net new assets and asset base</div>', unsafe_allow_html=True)
    left, right = st.columns((1.25, 0.75))
    with left:
        fig = go.Figure()
        fig.add_bar(x=flows["month_start"], y=flows["inflows_inr"] / 1e7, name="Inflows", marker_color=TEAL)
        fig.add_bar(x=flows["month_start"], y=-flows["outflows_inr"] / 1e7, name="Outflows", marker_color="#F59E0B")
        fig.add_scatter(
            x=flows["month_start"],
            y=flows["net_new_assets_inr"] / 1e7,
            name="Net new assets",
            mode="lines+markers",
            line=dict(color=GOLD, width=2.5),
        )
        fig.update_layout(barmode="relative", title="Monthly external flows (₹ Cr)")
        st.plotly_chart(style_fig(fig, height=360), width="stretch", config={"displayModeBar": False})
    with right:
        if len(channel):
            latest = channel[channel["month_start"] == channel["month_start"].max()]
            latest = latest[latest["total_assets_inr"] > 0]
            fig = px.pie(
                latest,
                names="channel_name",
                values="total_assets_inr",
                hole=0.58,
                color_discrete_sequence=PALETTE,
            )
            fig.update_traces(textinfo="percent", textfont_size=12)
            fig.update_layout(title="Latest asset mix by channel", showlegend=True)
            st.plotly_chart(style_fig(fig, height=360), width="stretch", config={"displayModeBar": False})
        else:
            st.info("No channels selected.")

    left, right = st.columns((1.25, 0.75))
    with left:
        fig = go.Figure()
        fig.add_scatter(
            x=assets["month_start"],
            y=assets["total_assets_inr"] / 1e7,
            name="Total assets",
            fill="tozeroy",
            line=dict(color=TEAL, width=2.5),
            fillcolor="rgba(15,118,110,0.12)",
        )
        fig.add_scatter(
            x=assets["month_start"],
            y=assets["fee_based_assets_inr"] / 1e7,
            name="Fee-based assets",
            line=dict(color=GOLD, width=2),
        )
        fig.update_layout(title="Asset base (₹ Cr)")
        st.plotly_chart(style_fig(fig, height=330), width="stretch", config={"displayModeBar": False})
    with right:
        top = advisors.head(10).sort_values("nna_ltm_inr")
        fig = go.Figure(
            go.Bar(
                x=top["nna_ltm_inr"] / 1e7,
                y=top["advisor_name"],
                orientation="h",
                marker_color=TEAL,
                text=[f"₹{v:,.0f} Cr" for v in top["nna_ltm_inr"] / 1e7],
                textposition="outside",
            )
        )
        fig.update_layout(title="Top-10 advisors by LTM NNA (₹ Cr)", showlegend=False)
        st.plotly_chart(style_fig(fig, height=330), width="stretch", config={"displayModeBar": False})

    with st.expander("Metric definitions and caveats", expanded=False):
        st.markdown(
            """
            **Net new assets (NNA)** = external client inflows (deposits, transfers in)
            minus external outflows (withdrawals, transfers out), in INR, by calendar month.
            Dividends, interest, fees and security trades are internal and excluded.

            **Fee-based asset share** = fee-based account balances ÷ total balances × 100.
            Fee-based accounts are managed portfolios, advisory accounts and fee-based brokerage.

            **12-month cohort retention** = share of an onboarding cohort with a positive
            asset balance twelve months later. It is an asset-presence proxy, not revenue retention.

            **Digital migration to advice** = digital-acquired clients with at least one
            completed `plan_created` event ÷ eligible digital clients onboarded at least 90 days
            before the observation end. This is a synthetic milestone, not a causal estimate.

            The synthetic closure process (and therefore retention) is a scenario assumption.
            All figures come from fabricated data.
            """
        )

# ---------------------------------------------------------------------------
# Flows and channels
# ---------------------------------------------------------------------------
elif nav == "Flows & channels":
    flows = q_flows(str(DB_PATH), start_month, end_month)
    if flows.empty:
        st.info("No months in the selected range.")
        st.stop()
    channel = q_channel(str(DB_PATH), start_month, end_month, tuple(selected_channels))
    flow_types = q_flow_types(str(DB_PATH), start_month, end_month)
    funnel = q_funnel(str(DB_PATH))
    migration = q_migration(str(DB_PATH))
    cohorts = q_migration_cohorts(str(DB_PATH))

    total_in = flows["inflows_inr"].sum()
    total_out = flows["outflows_inr"].sum()
    total_nna = flows["net_new_assets_inr"].sum()
    c1, c2, c3 = st.columns(3)
    with c1:
        card("Inflows in window", cr(total_in), f"{len(flows)} months")
    with c2:
        card("Outflows in window", cr(total_out))
    with c3:
        card("Net new assets in window", cr(total_nna))

    st.markdown('<div class="wo-section">Flow trend</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_bar(x=flows["month_start"], y=flows["inflows_inr"] / 1e7, name="Inflows", marker_color=TEAL)
    fig.add_bar(x=flows["month_start"], y=-flows["outflows_inr"] / 1e7, name="Outflows", marker_color="#F59E0B")
    fig.add_scatter(
        x=flows["month_start"],
        y=flows["net_new_assets_inr"] / 1e7,
        name="Net new assets",
        mode="lines+markers",
        line=dict(color=GOLD, width=2.5),
    )
    fig.update_layout(barmode="relative", title="Monthly external flows (₹ Cr)")
    st.plotly_chart(style_fig(fig, height=360), width="stretch", config={"displayModeBar": False})

    left, right = st.columns((1.1, 0.9))
    with left:
        st.markdown('<div class="wo-section">Channel mix · latest month</div>', unsafe_allow_html=True)
        if len(channel):
            latest = channel[channel["month_start"] == channel["month_start"].max()].copy()
            latest["assets_cr"] = latest["total_assets_inr"] / 1e7
            latest["nna_ltm_cr"] = latest["nna_ltm_inr"] / 1e7
            st.dataframe(
                latest[
                    ["channel_name", "channel_type", "clients", "assets_cr", "assets_share_pct", "fee_based_share_pct", "nna_ltm_cr"]
                ].rename(
                    columns={
                        "channel_name": "Channel",
                        "channel_type": "Type",
                        "clients": "Clients",
                        "assets_cr": "Assets (₹ Cr)",
                        "assets_share_pct": "Asset share %",
                        "fee_based_share_pct": "Fee-based share %",
                        "nna_ltm_cr": "NNA LTM (₹ Cr)",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Assets (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                    "NNA LTM (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                    "Asset share %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                    "Fee-based share %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
        else:
            st.info("No channel data for the selected filters.")
    with right:
        st.markdown('<div class="wo-section">Advice funnel · all clients</div>', unsafe_allow_html=True)
        if len(funnel):
            totals = funnel[["clients", "engaged_clients", "planned_clients", "fee_based_clients"]].sum()
            fig = go.Figure(
                go.Funnel(
                    y=["Clients", "Engaged", "Completed plan", "Fee-based client"],
                    x=[totals["clients"], totals["engaged_clients"], totals["planned_clients"], totals["fee_based_clients"]],
                    marker_color=[NAVY, TEAL, GOLD, "#2563EB"],
                    textinfo="value+percent initial",
                )
            )
            fig.update_layout(title="Client journey (count)")
            st.plotly_chart(style_fig(fig, height=300), width="stretch", config={"displayModeBar": False})

    st.markdown('<div class="wo-section">Flow-type detail and migration cohorts</div>', unsafe_allow_html=True)
    left, right = st.columns((0.9, 1.1))
    with left:
        if len(flow_types):
            summary = (
                flow_types.groupby(["flow_type", "direction"], as_index=False)
                .agg(nna_inr=("nna_inr", "sum"), flow_count=("flow_count", "sum"))
                .sort_values("nna_inr", ascending=False)
            )
            summary["nna_cr"] = summary["nna_inr"] / 1e7
            st.dataframe(
                summary[["flow_type", "direction", "flow_count", "nna_cr"]].rename(
                    columns={
                        "flow_type": "Flow type",
                        "direction": "Direction",
                        "flow_count": "Count",
                        "nna_cr": "NNA (₹ Cr)",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={"NNA (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f")},
            )
    with right:
        if len(cohorts):
            fig = go.Figure()
            fig.add_scatter(
                x=cohorts["cohort_month"],
                y=cohorts["migration_rate_pct"],
                mode="lines+markers",
                line=dict(color=GOLD, width=2),
                name="Migration rate",
            )
            fig.update_layout(title="Digital migration-to-advice rate by onboarding cohort (%)")
            st.plotly_chart(style_fig(fig, height=320), width="stretch", config={"displayModeBar": False})
        if len(migration):
            row = migration.iloc[0]
            st.markdown(
                f'<div class="wo-card"><div class="label">Digital migration summary</div>'
                f'<div class="value">{pct(row.migration_rate_pct)}</div>'
                f'<div class="sub">{num(row.migrated_clients)} migrated of {num(row.eligible_clients)} eligible digital clients</div></div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Advisor book
# ---------------------------------------------------------------------------
elif nav == "Advisor book":
    advisors = q_advisors(str(DB_PATH))
    if advisors.empty:
        st.info("No advisor data.")
        st.stop()
    top_q = advisors[advisors["productivity_quartile"] == 1]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Advisors", num(len(advisors)))
    with c2:
        card("Top-quartile LTM NNA", cr(top_q["nna_ltm_inr"].sum()))
    with c3:
        card("Median assets / client", cr(advisors["assets_per_client_inr"].median()))
    with c4:
        card("Advice meetings · LTM", num(advisors["meetings_ltm"].sum()), f"{num(advisors['plans_ltm'].sum())} plans created")

    left, right = st.columns((1.0, 1.0))
    with left:
        fig = px.scatter(
            advisors,
            x="clients",
            y="nna_ltm_inr",
            size="total_assets_inr",
            color="productivity_quartile",
            hover_name="advisor_name",
            color_continuous_scale=["#0F766E", "#5EEAD4", "#C9A227", "#B45309"],
            labels={"clients": "Clients", "nna_ltm_inr": "LTM NNA (₹)", "productivity_quartile": "Quartile"},
        )
        fig.update_yaxes(tickformat=".2s")
        fig.update_layout(title="Book size vs LTM NNA (bubble = assets)")
        st.plotly_chart(style_fig(fig, height=390), width="stretch", config={"displayModeBar": False})
    with right:
        table = advisors.copy()
        table["book_cr"] = table["total_assets_inr"] / 1e7
        table["nna_cr"] = table["nna_ltm_inr"] / 1e7
        table["apc_cr"] = table["assets_per_client_inr"] / 1e7
        st.dataframe(
            table[
                ["nna_rank", "advisor_name", "region", "clients", "book_cr", "nna_cr", "apc_cr", "productivity_quartile", "fee_based_share_pct"]
            ].rename(
                columns={
                    "nna_rank": "Rank",
                    "advisor_name": "Advisor",
                    "region": "Region",
                    "clients": "Clients",
                    "book_cr": "Book (₹ Cr)",
                    "nna_cr": "NNA LTM (₹ Cr)",
                    "apc_cr": "Assets/client (₹ Cr)",
                    "productivity_quartile": "Quartile",
                    "fee_based_share_pct": "Fee-based %",
                }
            ),
            width="stretch",
            hide_index=True,
            height=390,
            column_config={
                "Book (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                "NNA LTM (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                "Assets/client (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                "Fee-based %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
    st.markdown('<div class="wo-section">Advisor trend</div>', unsafe_allow_html=True)
    advisor_name = st.selectbox("Inspect an advisor", q_advisor_options(str(DB_PATH)))
    monthly = q_advisor_monthly(str(DB_PATH), advisor_name)
    if len(monthly):
        fig = go.Figure()
        fig.add_bar(x=monthly["month_start"], y=monthly["nna_inr"] / 1e7, name="Monthly NNA", marker_color=TEAL)
        fig.add_scatter(
            x=monthly["month_start"],
            y=monthly["total_assets_inr"] / 1e7,
            name="Assets",
            mode="lines+markers",
            line=dict(color=GOLD, width=2.5),
            yaxis="y2",
        )
        fig.update_layout(
            title=f"{advisor_name} · assets (₹ Cr) and monthly NNA (₹ Cr)",
            yaxis2=dict(overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(style_fig(fig, height=340), width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Client cohorts
# ---------------------------------------------------------------------------
elif nav == "Client cohorts":
    retention = q_retention(str(DB_PATH), start_month, end_month)
    segments = q_segments(str(DB_PATH))
    clients = q_top_clients(str(DB_PATH))
    if selected_segments:
        segments = segments[segments["segment"].isin(selected_segments)]
        clients = clients[clients["segment"].isin(selected_segments)]

    if retention.empty:
        st.info("No observed cohort months in the selected range.")
    else:
        n_cohorts = retention["cohort_month"].nunique()
        c1, c2, c3 = st.columns(3)
        with c1:
            card("Observed cohorts", num(n_cohorts))
        with c2:
            twelve = retention[retention["months_since_onboarding"] == 12]
            rate = (
                100 * twelve["retained_clients"].sum() / twelve["cohort_size"].sum()
                if len(twelve) and twelve["cohort_size"].sum()
                else None
            )
            card("12-month retention", pct(rate))
        with c3:
            card("Top clients shown", num(len(clients)))

        st.markdown('<div class="wo-section">Cohort retention heatmap</div>', unsafe_allow_html=True)
        pivot = retention.pivot_table(
            index="cohort_month",
            columns="months_since_onboarding",
            values="retention_rate_pct",
        )
        pivot = pivot.sort_index()
        fig = go.Figure(
            go.Heatmap(
                z=pivot.values,
                x=[f"M{c}" for c in pivot.columns],
                y=[pd.Timestamp(i).strftime("%b %Y") for i in pivot.index],
                colorscale=[[0, "#FEE2E2"], [0.5, "#FDE68A"], [1, "#0F766E"]],
                zmin=0,
                zmax=100,
                colorbar=dict(title="% retained"),
                hovertemplate="Cohort %{y}<br>Month %{x}<br>Retention %{z:.1f}%<extra></extra>",
            )
        )
        fig.update_layout(title="Retention by onboarding cohort and months since onboarding")
        st.plotly_chart(style_fig(fig, height=430), width="stretch", config={"displayModeBar": False})

        left, right = st.columns((1.0, 1.0))
        with left:
            fig = go.Figure()
            cohort_values = list(retention["cohort_month"].drop_duplicates().sort_values())[-8:]
            for cohort in cohort_values:
                sub = retention[retention["cohort_month"] == cohort]
                fig.add_scatter(
                    x=sub["months_since_onboarding"],
                    y=sub["retention_rate_pct"],
                    mode="lines+markers",
                    name=pd.Timestamp(cohort).strftime("%b %Y"),
                )
            fig.update_layout(title="Retention curves · latest cohorts", xaxis_title="Months since onboarding", yaxis_title="%")
            st.plotly_chart(style_fig(fig, height=350), width="stretch", config={"displayModeBar": False})
        with right:
            if len(segments):
                fig = px.bar(
                    segments.sort_values("total_assets_inr"),
                    x="total_assets_inr",
                    y="segment",
                    orientation="h",
                    color="fee_based_share_pct",
                    color_continuous_scale=["#BAE6FD", "#0F766E"],
                    labels={"total_assets_inr": "Assets", "segment": "", "fee_based_share_pct": "Fee-based %"},
                )
                fig.update_xaxes(tickformat=".2s")
                fig.update_layout(title="Latest assets by segment")
                st.plotly_chart(style_fig(fig, height=350), width="stretch", config={"displayModeBar": False})

        st.markdown('<div class="wo-section">Top clients by latest assets</div>', unsafe_allow_html=True)
        if len(clients):
            table = clients.copy()
            table["assets_cr"] = table["total_assets_inr"] / 1e7
            table["nna_cr"] = table["nna_ltm_inr"] / 1e7
            st.dataframe(
                table[
                    ["asset_rank", "client_id", "segment", "channel_name", "advisor_name", "assets_cr", "nna_cr", "fee_based_share_pct", "asset_decile"]
                ].rename(
                    columns={
                        "asset_rank": "Rank",
                        "client_id": "Client",
                        "segment": "Segment",
                        "channel_name": "Channel",
                        "advisor_name": "Advisor",
                        "assets_cr": "Assets (₹ Cr)",
                        "nna_cr": "NNA LTM (₹ Cr)",
                        "fee_based_share_pct": "Fee-based %",
                        "asset_decile": "Decile",
                    }
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Assets (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                    "NNA LTM (₹ Cr)": st.column_config.NumberColumn(format="₹%.1f"),
                    "Fee-based %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------
elif nav == "Data quality":
    quality = q_quality(str(DB_PATH))
    counts = q_counts(str(DB_PATH))
    manifest = d.load_manifest(DATA_DIR)
    failures = quality[quality["status"] != "PASS"]
    c1, c2, c3 = st.columns(3)
    with c1:
        card("Checks passed", f"{len(quality) - len(failures)} / {len(quality)}")
    with c2:
        card("Failures", num(len(failures)))
    with c3:
        card("Scenario seed", str(manifest.get("seed", "—")))

    if len(failures) == 0:
        st.success("All data-quality and seeded-invariant checks pass.")
    else:
        st.error(f"{len(failures)} checks failed. Inspect the table below before using the metrics.")
    display = quality.copy()
    display["status"] = display["status"].map({"PASS": "✅ PASS", "FAIL": "❌ FAIL"}).fillna(display["status"])
    st.dataframe(
        display[["status", "category", "check_name", "observed", "expected", "details"]].rename(
            columns={
                "status": "Status",
                "category": "Category",
                "check_name": "Check",
                "observed": "Observed",
                "expected": "Expected",
                "details": "What it proves",
            }
        ),
        width="stretch",
        hide_index=True,
        height=430,
    )

    left, right = st.columns((1.0, 1.0))
    with left:
        st.markdown('<div class="wo-section">Warehouse row counts</div>', unsafe_allow_html=True)
        st.dataframe(
            counts.rename(columns={"metric": "Relation", "value": "Rows"}),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown('<div class="wo-section">Scenario manifest</div>', unsafe_allow_html=True)
        st.json(
            {
                "scenario": manifest.get("scenario"),
                "seed": manifest.get("seed"),
                "clients": manifest.get("clients"),
                "advisors": manifest.get("advisors"),
                "months": manifest.get("months"),
                "window": f"{manifest.get('start_month')} → {manifest.get('end_month')}",
                "disclaimer": manifest.get("disclaimer"),
            }
        )
    with st.expander("What the checks cover", expanded=False):
        st.markdown(
            """
            - **Uniqueness:** primary keys for clients, accounts, advisors, transactions, snapshots, events and assignments.
            - **Referential integrity:** operational foreign keys and fact-to-dimension joins.
            - **SCD2:** no overlapping assignment intervals, exactly one current interval, no gaps, valid effective dates.
            - **Reconciliation:** asset recurrence, flow-to-snapshot NNA, fact-to-operational totals, one fact row per transaction/event.
            - **Validity:** non-negative balances, fee-rate consistency, transaction dates, account opening dates, closed-client balances.
            - **Seeded invariants:** scenario counts, transaction volume, fee-based share range, migration range, retention range, advisor quartile spread and channel asset ordering.
            - **Reproducibility:** tested separately with a fixed-seed fingerprint in the pytest suite.
            """
        )

# ---------------------------------------------------------------------------
# Governed NL query
# ---------------------------------------------------------------------------
elif nav == "Ask the data":
    engine = NLQEngine(Settings(data_dir=DATA_DIR), row_limit=200)
    examples = engine.examples()
    cols = st.columns(2)
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(example, key=f"example_{i}", width="stretch"):
                st.session_state["nlq_question"] = example
    with st.form("nlq_form"):
        question = st.text_input(
            "Question",
            value=st.session_state.get("nlq_question", "Show net new assets by month"),
            placeholder="e.g. Compare the latest channel mix",
        )
        submitted = st.form_submit_button("Run governed query", type="primary")
    if submitted and question.strip():
        result = engine.ask(question)
        st.session_state["nlq_result"] = result
    result = st.session_state.get("nlq_result")
    if result is not None:
        if result.error:
            st.error(result.error)
        else:
            st.markdown(
                f'<span class="wo-pill wo-source">source: {result.source}</span> '
                f'<span class="wo-caption">{result.notes}</span>',
                unsafe_allow_html=True,
            )
            st.code(result.sql, language="sql")
            st.dataframe(result.frame, width="stretch", hide_index=True)
    with st.expander("Security controls and allow-list", expanded=False):
        st.markdown(
            """
            - Only `SELECT` / `WITH ... SELECT` is accepted; one statement only.
            - Only the curated `analytics.kpi_*` / `analytics.v_*` views are allow-listed.
            - `INSERT`, `UPDATE`, `DELETE`, DDL, `PRAGMA`, `ATTACH`, `COPY`, comments, comma joins,
              file/table functions and string-literal `FROM` targets are denied.
            - An outer `LIMIT 200` is always applied.
            - Queries run on a **read-only** DuckDB connection.
            - The optional LLM path is disabled unless `WEALTHOPS_LLM_API_KEY` is set; failures fall back
              to the deterministic rules engine.
            """
        )
        st.code("\\n".join(f"analytics.{v}" for v in engine.allowlist), language="text")
