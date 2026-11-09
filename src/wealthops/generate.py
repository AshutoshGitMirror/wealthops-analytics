"""Deterministic synthetic data generation.

Everything here is fabricated.  The generator uses explicit, independent NumPy
RNG streams so that changing one table does not silently change another, and
so that a fixed seed produces byte-identical logical tables.

The planted relationships are *scenario assumptions*, not causal claims:

* Digital-acquired clients with more advisory touches are more likely to
  complete a financial plan (the "migration to advice" scenario).
* Advisory-channel clients have larger balances in the seeded distribution.
* Clients with a completed plan are less likely to attrite.
* Newer fee-based accounts make the fee-based asset share drift upward.
* Advisor books are uneven by design, producing a productivity spread.

None of these relationships are estimates from real client data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Settings, month_end

SEGMENTS = ["Emerging", "Mass Affluent", "Affluent", "HNI", "Ultra HNI"]
SEGMENT_MULTIPLIER = {
    "Emerging": 1.0,
    "Mass Affluent": 1.8,
    "Affluent": 3.4,
    "HNI": 6.0,
    "Ultra HNI": 10.0,
}
SEGMENT_MEDIAN_AUM = {
    "Emerging": 250_000.0,
    "Mass Affluent": 1_200_000.0,
    "Affluent": 6_000_000.0,
    "HNI": 30_000_000.0,
    "Ultra HNI": 120_000_000.0,
}
CHANNEL_FACTOR = {"DIGITAL": 0.65, "BRANCH": 1.0, "ADVISORY": 1.35}
CHANNEL_SEGMENT_PROBS = {
    "DIGITAL": [0.30, 0.50, 0.15, 0.05, 0.00],
    "BRANCH": [0.10, 0.40, 0.35, 0.13, 0.02],
    "ADVISORY": [0.00, 0.10, 0.40, 0.38, 0.12],
}
CHANNEL_ONBOARDING_WEIGHT = {"DIGITAL": 0.60, "BRANCH": 0.28, "ADVISORY": 0.12}
CITIES = [
    "Mumbai",
    "Thane",
    "Navi Mumbai",
    "Pune",
    "Bengaluru",
    "Delhi",
    "Gurugram",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Ahmedabad",
    "Jaipur",
]
REGIONS = ["Mumbai", "Pune", "Bengaluru", "Delhi NCR", "Hyderabad"]
RISK_BY_SEGMENT = {
    "Emerging": ["Conservative", "Moderate", "Growth"],
    "Mass Affluent": ["Moderate", "Growth", "Aggressive"],
    "Affluent": ["Moderate", "Growth", "Aggressive"],
    "HNI": ["Growth", "Aggressive"],
    "Ultra HNI": ["Growth", "Aggressive"],
}


def _rng(seed: int, stream: int) -> np.random.Generator:
    """Independent RNG stream for one logical table/step."""
    return np.random.default_rng([seed, stream])


def _prob_choice(
    rng: np.random.Generator,
    values: list[str],
    size: int,
    probs: list[float],
) -> np.ndarray:
    return rng.choice(np.asarray(values, dtype=object), size=size, p=np.asarray(probs))


def _month_end_for(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(month_end(ts.year, ts.month))


def _month_start_for(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(date(ts.year, ts.month, 1))


def _asof_advisor(
    rows: pd.DataFrame,
    assignments: pd.DataFrame,
    date_col: str,
) -> pd.DataFrame:
    """Attach the advisor whose SCD2 interval covers ``date_col``.

    ``merge_asof`` finds the latest assignment that starts on or before the
    event date; the interval check then rejects a row if that assignment has
    already ended.  The generator never produces overlaps, so this is exact.
    """
    left = rows.sort_values(date_col).copy()
    right = assignments.sort_values("effective_from").copy()
    right = right[["client_id", "advisor_id", "effective_from", "effective_to"]]
    merged = pd.merge_asof(
        left,
        right,
        left_on=date_col,
        right_on="effective_from",
        by="client_id",
        direction="backward",
    )
    valid = merged["effective_to"].isna() | (merged["effective_to"] >= merged[date_col])
    merged.loc[~valid, "advisor_id"] = None
    merged = merged.drop(columns=["effective_from", "effective_to"])
    return merged.sort_values(["client_id", date_col]).reset_index(drop=True)


def _build_advisors(settings: Settings) -> pd.DataFrame:
    rng = _rng(settings.seed, 1)
    n = settings.n_advisors
    specialty = np.array(
        (["Emerging"] * 6 + ["Mass Affluent"] * 9 + ["Affluent"] * 8 + ["HNI"] * 5 + ["Ultra HNI"] * 2),
        dtype=object,
    )
    if n != len(specialty):
        specialty = rng.choice(SEGMENTS, size=n)
    hire_start = date(2018, 1, 1)
    hire_days = (date(2025, 12, 31) - hire_start).days
    rows = []
    for i in range(n):
        hire = hire_start + timedelta(days=int(rng.integers(0, hire_days)))
        rows.append(
            {
                "advisor_id": f"ADV{i + 1:02d}",
                "advisor_name": f"Advisor {i + 1:02d}",
                "region": REGIONS[int(rng.integers(0, len(REGIONS)))],
                "segment_specialty": specialty[i],
                "hire_date": pd.Timestamp(hire),
                "status": "Active" if i < n - 1 else "Inactive",
            }
        )
    return pd.DataFrame(rows)


def _build_channels() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"channel_id": 1, "channel_code": "DIGITAL", "channel_name": "Digital Direct", "channel_type": "Digital"},
            {"channel_id": 2, "channel_code": "BRANCH", "channel_name": "Branch Network", "channel_type": "Branch"},
            {"channel_id": 3, "channel_code": "ADVISORY", "channel_name": "Advisory & Private Client", "channel_type": "Advisor-led"},
        ]
    )


def _build_clients(settings: Settings, channels: pd.DataFrame) -> pd.DataFrame:
    rng = _rng(settings.seed, 2)
    n = settings.n_clients
    channel_codes = channels["channel_code"].to_numpy()
    channel_ids = channels["channel_id"].to_numpy()
    channel_idx = rng.choice(
        np.arange(len(channel_codes), dtype=int),
        size=n,
        p=np.array([CHANNEL_ONBOARDING_WEIGHT[c] for c in channel_codes]),
    )
    channel_id = channel_ids[channel_idx]
    channel_code = channel_codes[channel_idx]

    segments = np.empty(n, dtype=object)
    for idx, code in enumerate(channel_codes):
        mask = channel_idx == idx
        if mask.any():
            segments[mask] = _prob_choice(
                rng, SEGMENTS, int(mask.sum()), CHANNEL_SEGMENT_PROBS[code]
            )

    start = pd.Timestamp(settings.start_month)
    end = pd.Timestamp(settings.end_month)
    pre_share = 0.55
    is_pre = rng.random(n) < pre_share
    onboarding = np.empty(n, dtype="datetime64[ns]")
    pre_start = pd.Timestamp(date(2023, 1, 1))
    pre_days = max((start - pre_start).days - 1, 1)
    onboarding[is_pre] = (
        pre_start + pd.to_timedelta(rng.integers(0, pre_days, int(is_pre.sum())), unit="D")
    ).to_numpy()

    in_window = ~is_pre
    n_window = int(in_window.sum())
    # New client acquisition grows gradually across the observation window.
    # Onboarding stops two months before the end so new balances have some
    # observed history and do not create a single artificial end-of-window spike.
    month_choices = np.arange(0, settings.months - 2)
    month_starts = pd.date_range(start, periods=settings.months - 2, freq="MS")
    weights = np.linspace(0.35, 1.0, len(month_choices))
    weights = weights / weights.sum()
    chosen = rng.choice(month_choices, size=n_window, p=weights)
    day_offsets = rng.integers(0, 28, size=n_window)
    onboarding[in_window] = (
        month_starts[chosen] + pd.to_timedelta(day_offsets, unit="D")
    ).to_numpy()
    onboarding = np.minimum(onboarding, np.datetime64(end - pd.Timedelta(days=15)))
    onboarding_ts = pd.to_datetime(onboarding)

    risk = np.empty(n, dtype=object)
    for seg in SEGMENTS:
        mask = segments == seg
        if mask.any():
            risk[mask] = _prob_choice(
                rng, RISK_BY_SEGMENT[seg], int(mask.sum()), [1 / len(RISK_BY_SEGMENT[seg])] * len(RISK_BY_SEGMENT[seg])
            )

    cities = _prob_choice(rng, CITIES, n, [0.20, 0.08, 0.05, 0.12, 0.16, 0.07, 0.07, 0.10, 0.06, 0.04, 0.03, 0.02])

    clients = pd.DataFrame(
        {
            "client_id": [f"CL{i + 1:06d}" for i in range(n)],
            "client_name": [f"Client {i + 1:06d}" for i in range(n)],
            "channel_id": channel_id.astype(int),
            "segment": segments,
            "risk_profile": risk,
            "city": cities,
            "onboarding_date": onboarding_ts,
            "status": "Active",
            "closed_date": pd.NaT,
        }
    )
    clients["channel_code"] = channel_code
    return clients


def _build_accounts(settings: Settings, clients: pd.DataFrame) -> pd.DataFrame:
    rng = _rng(settings.seed, 3)
    n = len(clients)
    clients = clients.reset_index(drop=True)
    target = np.empty(n)
    for seg, median in SEGMENT_MEDIAN_AUM.items():
        mask = (clients["segment"] == seg).to_numpy()
        if mask.any():
            target[mask] = rng.lognormal(
                mean=np.log(median), sigma=0.70 if seg != "Ultra HNI" else 0.55, size=int(mask.sum())
            )
    target *= clients["channel_code"].map(CHANNEL_FACTOR).to_numpy()
    target = np.maximum(target, 100_000)

    n_accounts = 1 + rng.poisson(0.65, n)
    n_accounts = np.where(clients["segment"].isin(["HNI", "Ultra HNI"]), n_accounts + 1, n_accounts)
    n_accounts = np.clip(n_accounts, 1, 3)

    start = pd.Timestamp(settings.start_month)
    end = pd.Timestamp(settings.end_month)
    account_rows: list[dict] = []
    account_no = 1
    fee_types = ["Managed Portfolio", "Advisory Account", "Fee-Based Brokerage"]
    non_fee_types = ["Self-Directed", "Cash Management"]
    for i, client in clients.iterrows():
        k = int(n_accounts[i])
        weights = rng.dirichlet(np.ones(k) * 1.4)
        opened_base = pd.Timestamp(client["onboarding_date"]) + pd.to_timedelta(
            int(rng.integers(0, 45)), unit="D"
        )
        opened_base = min(opened_base, end - pd.Timedelta(days=45))
        opened_base = max(opened_base, pd.Timestamp(client["onboarding_date"]), pd.Timestamp(date(2023, 1, 1)))
        fee_p = {"DIGITAL": 0.20, "BRANCH": 0.42, "ADVISORY": 0.75}[client["channel_code"]]
        # Newer vintages are more likely to be fee-based, by scenario design.
        fee_p = min(0.92, fee_p + max(0, (opened_base.year - 2023)) * 0.035)
        for j in range(k):
            is_fee = bool(rng.random() < fee_p)
            if is_fee:
                acct_type = fee_types[int(rng.choice(np.arange(3), p=[0.45, 0.35, 0.20]))]
                fee_bps = int(rng.integers(65, 146))
            else:
                acct_type = non_fee_types[int(rng.choice(np.arange(2), p=[0.75, 0.25]))]
                fee_bps = 0
            opened = opened_base + pd.to_timedelta(int(rng.integers(0, 45)), unit="D")
            opened = min(opened, end - pd.Timedelta(days=20))
            opened = max(opened, pd.Timestamp(client["onboarding_date"]))
            account_rows.append(
                {
                    "account_id": f"AC{account_no:06d}",
                    "client_id": client["client_id"],
                    "account_type": acct_type,
                    "opened_date": opened,
                    "status": "Active",
                    "fee_rate_bps": fee_bps,
                    "is_fee_based": is_fee,
                    "target_balance": float(target[i] * weights[j]),
                }
            )
            account_no += 1
    accounts = pd.DataFrame(account_rows)
    accounts["target_balance"] = accounts["target_balance"].clip(lower=50_000)
    accounts["opened_month_end"] = accounts["opened_date"].map(_month_end_for)
    return accounts


def _advisor_pool(advisor: pd.DataFrame, segment: str) -> np.ndarray:
    exact = advisor.loc[advisor["segment_specialty"] == segment, "advisor_id"].to_numpy()
    if len(exact) > 0:
        return exact
    adjacent = {
        "Emerging": ["Mass Affluent"],
        "Mass Affluent": ["Emerging", "Affluent"],
        "Affluent": ["Mass Affluent", "HNI"],
        "HNI": ["Affluent", "Ultra HNI"],
        "Ultra HNI": ["HNI"],
    }[segment]
    pool = advisor.loc[advisor["segment_specialty"].isin(adjacent), "advisor_id"].to_numpy()
    return pool if len(pool) > 0 else advisor["advisor_id"].to_numpy()


def _build_assignments(
    settings: Settings, clients: pd.DataFrame, advisors: pd.DataFrame
) -> pd.DataFrame:
    rng = _rng(settings.seed, 4)
    start = pd.Timestamp(settings.start_month)
    end = pd.Timestamp(settings.end_month)
    # Uneven book sizes are deliberate: they create a productivity spread.
    advisor_ids = advisors["advisor_id"].to_numpy()
    advisor_weights = rng.pareto(1.6, len(advisor_ids)) + 1.0
    advisor_weights = advisor_weights / advisor_weights.sum()

    rows: list[dict] = []
    assignment_no = 1
    for _, client in clients.iterrows():
        pool = _advisor_pool(advisors, client["segment"])
        # All advisors remain eligible; the Pareto draw is applied to the pool.
        pool = np.asarray(pool)
        p = advisor_weights[np.isin(advisor_ids, pool)]
        p = p / p.sum()
        first = str(rng.choice(pool, p=p))
        rows.append(
            {
                "assignment_id": f"AA{assignment_no:07d}",
                "client_id": client["client_id"],
                "advisor_id": first,
                "effective_from": pd.Timestamp(client["onboarding_date"]),
                "effective_to": pd.NaT,
                "assignment_reason": "Onboarding",
            }
        )
        assignment_no += 1

        if rng.random() < 0.18:
            lower = max(pd.Timestamp(client["onboarding_date"]) + pd.Timedelta(days=120), start)
            upper = end - pd.Timedelta(days=45)
            if lower < upper:
                reassignment = lower + pd.to_timedelta(
                    int(rng.integers(0, max((upper - lower).days, 1))), unit="D"
                )
                alternatives = pool[pool != first]
                if len(alternatives) == 0:
                    alternatives = advisor_ids[advisor_ids != first]
                p2 = advisor_weights[np.isin(advisor_ids, alternatives)]
                p2 = p2 / p2.sum()
                second = str(rng.choice(alternatives, p=p2))
                rows.append(
                    {
                        "assignment_id": f"AA{assignment_no:07d}",
                        "client_id": client["client_id"],
                        "advisor_id": second,
                        "effective_from": reassignment,
                        "effective_to": pd.NaT,
                        "assignment_reason": "Reassignment",
                    }
                )
                assignment_no += 1

    out = pd.DataFrame(rows).sort_values(["client_id", "effective_from"]).reset_index(drop=True)
    next_from = out.groupby("client_id")["effective_from"].shift(-1)
    out["effective_to"] = next_from - pd.Timedelta(days=1)
    out["is_current"] = out["effective_to"].isna()
    return out


def _build_engagement(
    settings: Settings,
    clients: pd.DataFrame,
    assignments: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = _rng(settings.seed, 5)
    end = pd.Timestamp(settings.end_month)
    rows: list[dict] = []
    event_no = 1

    def add(client_id: str, event_date: pd.Timestamp, event_type: str, duration: int, channel_id: int):
        nonlocal event_no
        rows.append(
            {
                "event_id": f"EV{event_no:08d}",
                "client_id": client_id,
                "event_date": pd.Timestamp(event_date).normalize(),
                "event_type": event_type,
                "duration_minutes": int(duration),
                "channel_id": int(channel_id),
            }
        )
        event_no += 1

    plan_rows: list[dict] = []
    for _, client in clients.iterrows():
        cid = client["client_id"]
        onboard = pd.Timestamp(client["onboarding_date"])
        channel = client["channel_code"]
        segment = client["segment"]
        add(cid, onboard, "onboarding", 30, client["channel_id"])

        base_lambda = {"DIGITAL": 2.2, "BRANCH": 4.2, "ADVISORY": 7.0}[channel]
        if segment in ("HNI", "Ultra HNI"):
            base_lambda *= 1.25
        usable_days = max((end - onboard).days, 1)
        n_touch = int(min(rng.poisson(base_lambda), 18))
        touch_dates = onboard + pd.to_timedelta(
            rng.integers(0, usable_days, n_touch), unit="D"
        )
        for dt in touch_dates:
            t = rng.random()
            if t < 0.42:
                add(cid, dt, "call", 20, client["channel_id"])
            elif t < 0.80:
                add(cid, dt, "meeting", 60, client["channel_id"])
            elif t < 0.88:
                add(cid, dt, "seminar", 120, client["channel_id"])
            else:
                add(cid, dt, "email", 0, client["channel_id"])

        n_login = int(min(rng.poisson({"DIGITAL": 3.2, "BRANCH": 1.4, "ADVISORY": 0.8}[channel]), 12))
        login_dates = onboard + pd.to_timedelta(
            rng.integers(0, usable_days, n_login), unit="D"
        )
        for dt in login_dates:
            add(cid, dt, "digital_login", 0, client["channel_id"])

        # Planted scenario assumption: more advisory touches -> higher plan rate.
        if (end - onboard).days >= 120:
            touch_count = int(n_touch)
            plan_p = {
                "DIGITAL": 0.08 + 0.040 * touch_count,
                "BRANCH": 0.24 + 0.030 * touch_count,
                "ADVISORY": 0.60 + 0.022 * touch_count,
            }[channel]
            plan_p = min(plan_p, 0.93)
            if rng.random() < plan_p:
                plan_date = onboard + pd.to_timedelta(
                    90 + int(rng.integers(0, max((end - onboard).days - 90, 1))), unit="D"
                )
                plan_date = min(plan_date, end - pd.Timedelta(days=20))
                add(cid, plan_date, "plan_created", 90, client["channel_id"])
                plan_rows.append({"client_id": cid, "plan_date": plan_date})
                if rng.random() < 0.65:
                    review_date = plan_date + pd.to_timedelta(
                        90 + int(rng.integers(0, 210)), unit="D"
                    )
                    if review_date <= end - pd.Timedelta(days=10):
                        add(cid, review_date, "plan_review", 45, client["channel_id"])

    events = pd.DataFrame(rows)
    events["event_date"] = pd.to_datetime(events["event_date"])
    events = _asof_advisor(events, assignments, "event_date")
    events = events.sort_values(["event_date", "client_id", "event_type"]).reset_index(drop=True)
    events["event_id"] = [f"EV{i + 1:08d}" for i in range(len(events))]
    events["is_planning_event"] = events["event_type"].isin(["plan_created", "plan_review"])
    plans = pd.DataFrame(plan_rows)
    return events, plans


def _build_closures(
    settings: Settings,
    clients: pd.DataFrame,
    events: pd.DataFrame,
    plans: pd.DataFrame,
    accounts: pd.DataFrame,
) -> pd.DataFrame:
    rng = _rng(settings.seed, 6)
    end = pd.Timestamp(settings.end_month)
    planned = set(plans["client_id"]) if len(plans) else set()
    last_event = events.groupby("client_id")["event_date"].max().to_dict()
    max_opened = accounts.groupby("client_id")["opened_date"].max().to_dict()
    out = clients.copy()
    statuses = []
    closed_dates = []
    for _, client in out.iterrows():
        cid = client["client_id"]
        onboard = pd.Timestamp(client["onboarding_date"])
        base_p = 0.050 if cid in planned else 0.160
        eligible_start = onboard + pd.Timedelta(days=90)
        last = pd.Timestamp(last_event.get(cid, onboard)) + pd.Timedelta(days=30)
        opened = pd.Timestamp(max_opened.get(cid, onboard)) + pd.Timedelta(days=30)
        lower = max(eligible_start, last, opened)
        upper = end - pd.Timedelta(days=10)
        if rng.random() < base_p and lower < upper:
            close_date = lower + pd.to_timedelta(
                int(rng.integers(0, max((upper - lower).days, 1))), unit="D"
            )
            statuses.append("Closed")
            closed_dates.append(pd.Timestamp(close_date).normalize())
        else:
            statuses.append("Dormant" if rng.random() < 0.07 else "Active")
            closed_dates.append(pd.NaT)
    out["status"] = statuses
    out["closed_date"] = closed_dates
    out["closed_month_end"] = out["closed_date"].map(
        lambda x: _month_end_for(x) if pd.notna(x) else pd.NaT
    )
    return out


def _month_grid(settings: Settings) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month_end": [pd.Timestamp(d) for d in settings.month_ends],
            "month_start": [pd.Timestamp(date(d.year, d.month, 1)) for d in settings.month_ends],
            "month_idx": np.arange(settings.months),
        }
    )


def _build_flows_and_snapshots(
    settings: Settings,
    clients: pd.DataFrame,
    accounts: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = _rng(settings.seed, 7)
    start = pd.Timestamp(settings.start_month)
    end = pd.Timestamp(settings.end_month)
    months = _month_grid(settings)

    accounts = accounts.merge(
        clients[["client_id", "closed_date", "closed_month_end", "channel_id", "segment", "channel_code"]],
        on="client_id",
        how="left",
    )
    grid = accounts.merge(months, how="cross")
    grid = grid[grid["month_end"] >= grid["opened_month_end"]].copy()
    grid = grid[grid["month_end"] <= end].copy()
    grid = grid[grid["closed_month_end"].isna() | (grid["month_end"] <= grid["closed_month_end"])].copy()
    grid = grid.sort_values(["account_id", "month_idx"]).reset_index(drop=True)
    grid["active_idx"] = grid.groupby("account_id").cumcount()
    grid["ref_balance"] = grid["target_balance"] * (1.0035 ** grid["active_idx"])
    grid["ref_balance"] = grid["ref_balance"].clip(lower=10_000)

    n = len(grid)
    tx_rows: list[pd.DataFrame] = []

    def add_mask_tx(
        mask: np.ndarray,
        tx_type: str,
        direction: str,
        amounts: np.ndarray,
        is_net_new: bool,
    ) -> None:
        if not mask.any():
            return
        sub = grid.loc[mask, ["account_id", "month_end", "month_start", "opened_date", "ref_balance", "is_fee_based"]].copy()
        sub["transaction_type"] = tx_type
        sub["direction"] = direction
        sub["amount_inr"] = np.round(amounts[mask], 2)
        sub["is_net_new"] = is_net_new
        sub["day_offset"] = rng.integers(0, 27, int(mask.sum()))
        candidate = sub["month_start"] + pd.to_timedelta(sub["day_offset"], unit="D")
        sub["transaction_date"] = candidate.where(candidate >= sub["opened_date"], sub["opened_date"])
        tx_rows.append(sub)

    ref = grid["ref_balance"].to_numpy()

    deposit_mask = rng.random(n) < 0.135
    add_mask_tx(
        deposit_mask,
        "deposit",
        "inflow",
        ref * rng.uniform(0.006, 0.040, n),
        True,
    )
    transfer_in_mask = rng.random(n) < 0.050
    add_mask_tx(
        transfer_in_mask,
        "transfer_in",
        "inflow",
        ref * rng.uniform(0.010, 0.085, n),
        True,
    )
    withdrawal_mask = rng.random(n) < 0.085
    add_mask_tx(
        withdrawal_mask,
        "withdrawal",
        "outflow",
        -np.minimum(ref * rng.uniform(0.004, 0.030, n), ref * 0.20),
        True,
    )
    transfer_out_mask = rng.random(n) < 0.028
    add_mask_tx(
        transfer_out_mask,
        "transfer_out",
        "outflow",
        -np.minimum(ref * rng.uniform(0.008, 0.055, n), ref * 0.25),
        True,
    )
    dividend_mask = grid["month_end"].dt.month.isin([3, 6, 9, 12]).to_numpy() & (rng.random(n) < 0.65)
    add_mask_tx(
        dividend_mask,
        "dividend",
        "internal",
        ref * rng.uniform(0.002, 0.007, n),
        False,
    )
    interest_mask = rng.random(n) < 0.45
    add_mask_tx(
        interest_mask,
        "interest",
        "internal",
        ref * rng.uniform(0.0005, 0.0018, n),
        False,
    )

    fee_mask = grid["is_fee_based"].to_numpy()
    fee_amounts = -np.round(ref * grid["fee_rate_bps"].to_numpy() / 10_000 / 12, 2)
    add_mask_tx(fee_mask, "fee", "internal", fee_amounts, False)

    buy_mask = rng.random(n) < 0.045
    add_mask_tx(buy_mask, "buy", "internal", ref * rng.uniform(0.005, 0.030, n), False)
    sell_mask = rng.random(n) < 0.030
    add_mask_tx(sell_mask, "sell", "internal", ref * rng.uniform(0.005, 0.030, n), False)

    flows = pd.concat(tx_rows, ignore_index=True)
    flows["month_end"] = flows["transaction_date"].map(_month_end_for)
    flows["client_id"] = flows["account_id"].map(accounts.set_index("account_id")["client_id"])
    flows["channel_id"] = flows["account_id"].map(accounts.set_index("account_id")["channel_id"])
    flows["is_fee_based"] = flows["account_id"].map(accounts.set_index("account_id")["is_fee_based"])

    # Initial funding for accounts opened inside the observation window.  This
    # is an external inflow and therefore part of net new assets.
    new_accounts = accounts[accounts["opened_date"] >= start].copy()
    if len(new_accounts) > 0:
        initial = new_accounts[["account_id", "client_id", "channel_id", "opened_date", "target_balance", "is_fee_based"]].copy()
        initial["transaction_type"] = "deposit"
        initial["direction"] = "inflow"
        initial["amount_inr"] = initial["target_balance"].round(2)
        initial["is_net_new"] = True
        initial["transaction_date"] = initial["opened_date"]
        initial["month_end"] = initial["opened_date"].map(_month_end_for)
        flows = pd.concat([flows, initial], ignore_index=True)

    # Aggregate the asset-affecting flows for the monthly recurrence.
    flows["_nna"] = np.where(flows["is_net_new"], flows["amount_inr"], 0.0)
    flows["_income"] = np.where(flows["transaction_type"].isin(["dividend", "interest"]), flows["amount_inr"], 0.0)
    flows["_fee"] = np.where(flows["transaction_type"] == "fee", -flows["amount_inr"], 0.0)

    agg = (
        flows.groupby(["account_id", "month_end"], as_index=False)
        .agg(nna=("_nna", "sum"), income=("_income", "sum"), fee=("_fee", "sum"))
    )
    grid = grid.merge(agg, on=["account_id", "month_end"], how="left")
    for col in ["nna", "income", "fee"]:
        grid[col] = grid[col].fillna(0.0)

    # Common market factor + idiosyncratic noise; stored so reconciliation is
    # exact and auditable.
    market_factor = rng.normal(0.0060, 0.0220, settings.months)
    account_ids = accounts["account_id"].to_numpy()
    account_index = pd.Index(account_ids)
    grid["market_return_pct"] = market_factor[grid["month_idx"].to_numpy()] + rng.normal(0.0, 0.0120, len(grid))
    grid["acct_pos"] = account_index.get_indexer(grid["account_id"])
    n_accounts = len(accounts)
    n_months = settings.months

    # Matrix recurrence.  For accounts opened before the window the first
    # observed beginning balance is the account's target balance; for accounts
    # opened inside the window the beginning balance is zero and the initial
    # funding deposit is in NNA.
    nna_m = np.zeros((n_accounts, n_months))
    income_m = np.zeros((n_accounts, n_months))
    fee_m = np.zeros((n_accounts, n_months))
    ret_m = np.zeros((n_accounts, n_months))
    for row in grid.itertuples(index=False):
        nna_m[row.acct_pos, row.month_idx] = row.nna
        income_m[row.acct_pos, row.month_idx] = row.income
        fee_m[row.acct_pos, row.month_idx] = row.fee
        ret_m[row.acct_pos, row.month_idx] = row.market_return_pct

    first_idx = grid.groupby("account_id")["month_idx"].min()
    first_idx = first_idx.reindex(account_ids).to_numpy()
    opened_before = (accounts["opened_date"] < start).to_numpy()
    opening = np.where(opened_before, accounts["target_balance"].to_numpy(), 0.0)

    beginning_m = np.zeros((n_accounts, n_months))
    growth_m = np.zeros((n_accounts, n_months))
    ending_m = np.zeros((n_accounts, n_months))
    balance = np.zeros(n_accounts)
    for m in range(n_months):
        active = (m >= first_idx) & (m >= 0)
        beg = np.where(m == np.where(opened_before, first_idx, -1), opening, balance)
        beg = np.where(active, beg, 0.0)
        growth = beg * ret_m[:, m]
        ending = beg + growth + nna_m[:, m] + income_m[:, m] - fee_m[:, m]
        # Defensive: the seeded draw should never go negative.  If it does,
        # surface a clear error rather than silently fabricating assets.
        if (ending < -1e-6).any():
            bad = accounts.loc[ending < -1e-6, "account_id"].tolist()[:5]
            raise ValueError(f"Synthetic balance went negative for accounts: {bad}")
        beginning_m[:, m] = beg
        growth_m[:, m] = growth
        ending_m[:, m] = ending
        balance = ending

    grid["beginning_assets_inr"] = beginning_m[grid["acct_pos"].to_numpy(), grid["month_idx"].to_numpy()]
    grid["market_growth_inr"] = growth_m[grid["acct_pos"].to_numpy(), grid["month_idx"].to_numpy()]
    grid["ending_assets_inr"] = ending_m[grid["acct_pos"].to_numpy(), grid["month_idx"].to_numpy()]
    grid["cash_ratio"] = 0.03 + 0.05 * rng.random(len(grid))
    grid["cash_balance_inr"] = grid["ending_assets_inr"] * grid["cash_ratio"]
    grid["market_value_inr"] = grid["ending_assets_inr"] - grid["cash_balance_inr"]
    grid["fee_amount_inr"] = grid["fee"]

    # Close-out external transfer for attrited clients, so assets and flows
    # reconcile to zero on the closure month.
    closed = clients[clients["closed_date"].notna()][["client_id", "closed_date", "closed_month_end"]]
    close_rows = []
    if len(closed) > 0:
        snap = grid.merge(closed[["client_id", "closed_date", "closed_month_end"]], on="client_id", how="inner", suffixes=("", "_c"))
        snap = snap[snap["month_end"] == snap["closed_month_end"]].copy()
        for row in snap.itertuples(index=False):
            amount = -float(row.ending_assets_inr)
            if abs(amount) < 0.01:
                continue
            close_rows.append(
                {
                    "account_id": row.account_id,
                    "month_end": row.month_end,
                    "month_start": row.month_start,
                    "ref_balance": row.ref_balance,
                    "is_fee_based": row.is_fee_based,
                    "transaction_type": "transfer_out",
                    "direction": "outflow",
                    "amount_inr": round(amount, 2),
                    "is_net_new": True,
                    "transaction_date": pd.Timestamp(row.closed_date),
                    "client_id": row.client_id,
                    "channel_id": row.channel_id,
                    "_nna": round(amount, 2),
                    "_income": 0.0,
                    "_fee": 0.0,
                }
            )
            mask = (grid["account_id"] == row.account_id) & (grid["month_end"] == row.month_end)
            grid.loc[mask, "nna"] = grid.loc[mask, "nna"] + amount
            grid.loc[mask, "ending_assets_inr"] = 0.0
            grid.loc[mask, "cash_balance_inr"] = 0.0
            grid.loc[mask, "market_value_inr"] = 0.0
        if close_rows:
            flows = pd.concat([flows, pd.DataFrame(close_rows)], ignore_index=True)

    # Remove helper columns and finalise the operational objects.
    snapshot_cols = [
        "account_id",
        "client_id",
        "month_end",
        "beginning_assets_inr",
        "market_growth_inr",
        "net_new_assets_inr",
        "internal_income_inr",
        "fee_amount_inr",
        "market_return_pct",
        "market_value_inr",
        "cash_balance_inr",
        "total_assets_inr",
    ]
    grid = grid.rename(columns={"net_new_assets_inr": "net_new_assets_inr"})
    grid["net_new_assets_inr"] = grid["nna"]
    grid["internal_income_inr"] = grid["income"]
    grid["fee_amount_inr"] = grid["fee"]
    grid["total_assets_inr"] = grid["ending_assets_inr"]
    snapshots = grid[snapshot_cols].copy()
    snapshots = snapshots.sort_values(["month_end", "account_id"]).reset_index(drop=True)
    snapshots["snapshot_id"] = [f"MS{i + 1:08d}" for i in range(len(snapshots))]

    flows = flows.drop(columns=[c for c in flows.columns if c.startswith("_") or c in {"month_end", "month_start", "ref_balance", "day_offset"}], errors="ignore")
    flows = flows.sort_values(["transaction_date", "account_id", "transaction_type"]).reset_index(drop=True)
    flows["transaction_id"] = [f"TX{i + 1:09d}" for i in range(len(flows))]
    flows["transaction_date"] = pd.to_datetime(flows["transaction_date"]).dt.normalize()
    flows["amount_inr"] = flows["amount_inr"].round(2)
    flows = flows[
        [
            "transaction_id",
            "account_id",
            "client_id",
            "channel_id",
            "transaction_date",
            "transaction_type",
            "direction",
            "amount_inr",
            "is_net_new",
            "is_fee_based",
        ]
    ].copy()

    # Drop snapshots after closure (the close month is retained with zero assets).
    if len(closed) > 0:
        close_map = closed.set_index("client_id")["closed_month_end"].to_dict()
        keep = []
        for row in snapshots.itertuples(index=False):
            cm = close_map.get(row.client_id)
            keep.append(pd.isna(cm) or row.month_end <= cm)
        snapshots = snapshots.loc[keep].reset_index(drop=True)
        snapshots["snapshot_id"] = [f"MS{i + 1:08d}" for i in range(len(snapshots))]

    return flows, snapshots


@dataclass
class GeneratedData:
    channels: pd.DataFrame
    advisors: pd.DataFrame
    clients: pd.DataFrame
    accounts: pd.DataFrame
    assignments: pd.DataFrame
    transactions: pd.DataFrame
    snapshots: pd.DataFrame
    engagements: pd.DataFrame

    def frames(self) -> dict[str, pd.DataFrame]:
        return {
            "channel": self.channels,
            "advisor": self.advisors,
            "client": self.clients,
            "account": self.accounts,
            "advisor_assignment": self.assignments,
            "transaction": self.transactions,
            "monthly_asset_snapshot": self.snapshots,
            "engagement_event": self.engagements,
        }


def generate_data(settings: Settings) -> GeneratedData:
    """Build all synthetic tables in memory.  Pure with respect to the seed."""
    channels = _build_channels()
    advisors = _build_advisors(settings)
    clients = _build_clients(settings, channels)
    accounts = _build_accounts(settings, clients)
    assignments = _build_assignments(settings, clients, advisors)
    engagements, plans = _build_engagement(settings, clients, assignments)
    clients = _build_closures(settings, clients, engagements, plans, accounts)
    transactions, snapshots = _build_flows_and_snapshots(settings, clients, accounts)

    # Account-level target columns are generator internals, not operational data.
    accounts_out = accounts[
        ["account_id", "client_id", "account_type", "opened_date", "status", "fee_rate_bps", "is_fee_based"]
    ].copy()
    clients_out = clients[
        ["client_id", "client_name", "channel_id", "segment", "risk_profile", "city", "onboarding_date", "status", "closed_date"]
    ].copy()

    # Plan columns are internal; drop any accidental helper columns from events.
    engagements_out = engagements[
        ["event_id", "client_id", "advisor_id", "channel_id", "event_date", "event_type", "duration_minutes", "is_planning_event"]
    ].copy()

    return GeneratedData(
        channels=channels,
        advisors=advisors,
        clients=clients_out,
        accounts=accounts_out,
        assignments=assignments,
        transactions=transactions,
        snapshots=snapshots,
        engagements=engagements_out,
    )


def write_raw(data: GeneratedData, raw_dir: Path) -> dict[str, Path]:
    """Write each table to parquet and return the paths."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, frame in data.frames().items():
        path = raw_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        paths[name] = path
    return paths


def frame_fingerprint(frame: pd.DataFrame) -> str:
    """Stable logical fingerprint, independent of parquet encoding."""
    csv = frame.to_csv(index=False, date_format="%Y-%m-%d")
    return hashlib.sha256(csv.encode("utf-8")).hexdigest()


def dataset_fingerprint(data: GeneratedData) -> dict[str, str]:
    return {name: frame_fingerprint(frame) for name, frame in data.frames().items()}
