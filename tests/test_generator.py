"""Generator-level invariants and determinism tests (no database required)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wealthops.config import Settings
from wealthops.generate import dataset_fingerprint, generate_data, write_raw


@pytest.fixture(scope="module")
def small(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    return Settings(
        n_clients=260,
        n_advisors=8,
        data_dir=tmp_path_factory.mktemp("generator-data"),
        export_dir=tmp_path_factory.mktemp("generator-exports"),
    )


@pytest.fixture(scope="module")
def data(small: Settings):
    return generate_data(small)


def test_declared_counts_and_generic_labels(data, small: Settings) -> None:
    assert len(data.channels) == small.n_channels
    assert len(data.advisors) == small.n_advisors
    assert len(data.clients) == small.n_clients
    assert data.clients["client_id"].is_unique
    assert data.accounts["account_id"].is_unique
    assert data.advisors["advisor_id"].is_unique
    assert data.clients["client_name"].str.startswith("Client ").all()
    assert data.advisors["advisor_name"].str.startswith("Advisor ").all()
    assert set(data.channels["channel_code"]) == {"DIGITAL", "BRANCH", "ADVISORY"}


def test_generator_referential_integrity(data) -> None:
    client_ids = set(data.clients["client_id"])
    advisor_ids = set(data.advisors["advisor_id"])
    account_ids = set(data.accounts["account_id"])
    channel_ids = set(data.channels["channel_id"])

    # Clients
    assert set(data.clients["channel_id"]).issubset(channel_ids)

    # Accounts
    assert set(data.accounts["client_id"]).issubset(client_ids)

    # Advisor assignments
    assert set(data.assignments["client_id"]).issubset(client_ids)
    assert set(data.assignments["advisor_id"]).issubset(advisor_ids)

    # Transactions
    assert set(data.transactions["account_id"]).issubset(account_ids)
    assert set(data.transactions["client_id"]).issubset(client_ids)
    assert set(data.transactions["channel_id"]).issubset(channel_ids)

    # Snapshots
    assert set(data.snapshots["account_id"]).issubset(account_ids)
    assert set(data.snapshots["client_id"]).issubset(client_ids)

    # Engagements
    assert set(data.engagements["client_id"]).issubset(client_ids)
    assert set(data.engagements["advisor_id"]).issubset(advisor_ids)
    assert set(data.engagements["channel_id"]).issubset(channel_ids)


def test_dates_and_balances_are_valid(data, small: Settings) -> None:
    window_start = pd.Timestamp(small.month_ends[0]).replace(day=1)
    end = pd.Timestamp(small.end_month)
    assert (data.clients["onboarding_date"] <= end).all()
    assert (data.accounts["opened_date"] <= end).all()
    assert (data.clients["onboarding_date"] <= data.accounts["opened_date"].max()).all()
    assert data.snapshots["month_end"].between(window_start, end).all()
    assert data.transactions["transaction_date"].between(window_start, end).all()
    assert (data.engagements["event_date"] <= end).all()
    assert (data.engagements["event_date"] >= data.clients["onboarding_date"].min()).all()

    assert (data.snapshots["total_assets_inr"] >= 0).all()
    assert np.isfinite(data.snapshots["total_assets_inr"]).all()
    assert np.isfinite(data.transactions["amount_inr"]).all()
    assert (data.transactions["amount_inr"] != 0).all()


def test_snapshot_recurrence_is_exact(data) -> None:
    frame = data.snapshots
    reconstructed = (
        frame["beginning_assets_inr"]
        + frame["market_growth_inr"]
        + frame["net_new_assets_inr"]
        + frame["internal_income_inr"]
        - frame["fee_amount_inr"]
    )
    assert np.allclose(reconstructed, frame["total_assets_inr"], atol=0.05)


def test_net_new_flows_have_expected_signs(data) -> None:
    net_new = data.transactions[data.transactions["is_net_new"]]
    assert set(net_new["transaction_type"]) <= {
        "deposit",
        "transfer_in",
        "withdrawal",
        "transfer_out",
    }
    inflows = net_new[net_new["direction"] == "inflow"]
    outflows = net_new[net_new["direction"] == "outflow"]
    assert (inflows["amount_inr"] > 0).all()
    assert (outflows["amount_inr"] < 0).all()
    internal = data.transactions[~data.transactions["is_net_new"]]
    assert set(internal["transaction_type"]) <= {
        "dividend",
        "interest",
        "fee",
        "buy",
        "sell",
    }


def test_closed_clients_have_no_snapshots_after_closure(data) -> None:
    closed = data.clients[data.clients["status"] == "Closed"]
    assert len(closed) > 0
    merged = data.snapshots.merge(
        closed[["client_id", "closed_date"]], on="client_id", how="inner"
    )
    assert len(merged) > 0
    closure_month_end = pd.to_datetime(merged["closed_date"]).dt.to_period("M").dt.end_time.dt.normalize()
    assert (merged["month_end"] <= closure_month_end).all()
    # The closure month is retained as a zero-balance row so NNA reconciles.
    final_rows = merged[merged["month_end"] == closure_month_end]
    assert (final_rows["total_assets_inr"] == 0).all()


def test_scd2_assignments_are_non_overlapping(data) -> None:
    assignments = data.assignments
    current_counts = assignments[assignments["is_current"]].groupby("client_id").size()
    assert (current_counts == 1).all()
    assert len(current_counts) == len(data.clients)
    assert (assignments["effective_from"] <= assignments["effective_to"].fillna(pd.Timestamp.max)).all()

    for _, group in assignments.groupby("client_id"):
        ordered = group.sort_values("effective_from")
        ends = ordered["effective_to"].tolist()
        starts = ordered["effective_from"].tolist()
        for idx in range(1, len(ordered)):
            previous_end = ends[idx - 1]
            assert previous_end is not None and previous_end < starts[idx]


def test_generation_is_deterministic(small: Settings) -> None:
    first = dataset_fingerprint(generate_data(small))
    second = dataset_fingerprint(generate_data(small))
    assert first == second
    assert set(first) == {
        "channel",
        "advisor",
        "client",
        "account",
        "advisor_assignment",
        "transaction",
        "monthly_asset_snapshot",
        "engagement_event",
    }


def test_different_seed_changes_data(small: Settings) -> None:
    from dataclasses import replace

    first = dataset_fingerprint(generate_data(small))
    second = dataset_fingerprint(generate_data(replace(small, seed=small.seed + 1)))
    assert first["client"] != second["client"]
    assert first["transaction"] != second["transaction"]


def test_write_raw_roundtrip(small: Settings, data) -> None:
    paths = write_raw(data, small.raw_dir)
    assert len(paths) == len(data.frames())
    for name, path in paths.items():
        assert path.exists()
        loaded = pd.read_parquet(path)
        assert len(loaded) == len(data.frames()[name]), name
    assert (small.raw_dir / "_manifest.json").exists() is False
