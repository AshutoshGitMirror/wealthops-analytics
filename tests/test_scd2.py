"""SCD2 assignment and as-of attribution tests."""

from __future__ import annotations


def test_exactly_one_current_assignment_per_client(query) -> None:
    bad = query(
        """
        SELECT client_id, COUNT(*) AS n
        FROM ops.advisor_assignment
        WHERE is_current
        GROUP BY 1 HAVING COUNT(*) <> 1
        """
    )
    assert bad.empty
    current = query("SELECT COUNT(*) AS n FROM ops.advisor_assignment WHERE is_current").iloc[0, 0]
    clients = query("SELECT COUNT(*) AS n FROM ops.client").iloc[0, 0]
    assert int(current) == int(clients)


def test_no_overlapping_or_inverted_intervals(query) -> None:
    inverted = query(
        """
        SELECT COUNT(*) AS n FROM ops.advisor_assignment
        WHERE effective_to IS NOT NULL AND effective_to < effective_from
        """
    ).iloc[0, 0]
    assert int(inverted) == 0

    overlaps = query(
        """
        SELECT COUNT(*) AS n
        FROM ops.advisor_assignment a
        JOIN ops.advisor_assignment b
          ON a.client_id = b.client_id
         AND a.assignment_id < b.assignment_id
         AND a.effective_from <= COALESCE(b.effective_to, DATE '9999-12-31')
         AND b.effective_from <= COALESCE(a.effective_to, DATE '9999-12-31')
        """
    ).iloc[0, 0]
    assert int(overlaps) == 0


def test_assignment_starts_are_contiguous(query) -> None:
    gaps = query(
        """
        WITH ordered AS (
            SELECT client_id, effective_from, effective_to,
                   LEAD(effective_from) OVER (PARTITION BY client_id ORDER BY effective_from) AS next_from
            FROM ops.advisor_assignment
        )
        SELECT COUNT(*) AS n
        FROM ordered
        WHERE next_from IS NOT NULL
          AND (effective_to IS NULL OR next_from <> effective_to + INTERVAL 1 DAY)
        """
    ).iloc[0, 0]
    assert int(gaps) == 0


def test_assignments_do_not_predate_onboarding(query) -> None:
    early = query(
        """
        SELECT COUNT(*) AS n
        FROM analytics.dim_advisor_assignment aa
        JOIN analytics.dim_client c ON c.client_key = aa.client_key
        WHERE aa.effective_from < c.onboarding_date
        """
    ).iloc[0, 0]
    assert int(early) == 0


def test_initial_assignment_matches_onboarding_date(query) -> None:
    mismatches = query(
        """
        WITH initial_assignment AS (
            SELECT client_id, MIN(effective_from) AS initial_from
            FROM ops.advisor_assignment
            GROUP BY 1
        )
        SELECT COUNT(*) AS n
        FROM initial_assignment ia
        JOIN ops.client c ON c.client_id = ia.client_id
        WHERE ia.initial_from <> c.onboarding_date
        """
    ).iloc[0, 0]
    assert int(mismatches) == 0


def test_dimension_assignment_row_count_matches_operational(query) -> None:
    operational = query("SELECT COUNT(*) AS n FROM ops.advisor_assignment").iloc[0, 0]
    dimension = query("SELECT COUNT(*) AS n FROM analytics.dim_advisor_assignment").iloc[0, 0]
    assert int(operational) == int(dimension)


def test_current_assignment_view_covers_every_client(query) -> None:
    missing = query(
        """
        SELECT COUNT(*) AS n
        FROM analytics.dim_client c
        LEFT JOIN analytics.v_client_current_advisor a ON a.client_key = c.client_key
        WHERE a.client_key IS NULL
        """
    ).iloc[0, 0]
    assert int(missing) == 0


def test_flow_facts_use_the_as_of_assignment(query) -> None:
    mismatches = query(
        """
        SELECT COUNT(*) AS n
        FROM analytics.fact_flows f
        LEFT JOIN analytics.dim_advisor_assignment aa
          ON aa.client_key = f.client_key
         AND f.flow_date BETWEEN aa.effective_from
             AND COALESCE(aa.effective_to, DATE '9999-12-31')
        WHERE aa.assignment_key IS NULL OR aa.advisor_key <> f.advisor_key
        """
    ).iloc[0, 0]
    assert int(mismatches) == 0


def test_asset_facts_use_the_as_of_assignment(query) -> None:
    mismatches = query(
        """
        SELECT COUNT(*) AS n
        FROM analytics.fact_monthly_assets f
        LEFT JOIN analytics.dim_advisor_assignment aa
          ON aa.client_key = f.client_key
         AND f.month_end BETWEEN aa.effective_from
             AND COALESCE(aa.effective_to, DATE '9999-12-31')
        WHERE aa.assignment_key IS NULL OR aa.advisor_key <> f.advisor_key
        """
    ).iloc[0, 0]
    assert int(mismatches) == 0


def test_engagement_facts_use_the_as_of_assignment(query) -> None:
    mismatches = query(
        """
        SELECT COUNT(*) AS n
        FROM analytics.fact_engagement f
        LEFT JOIN analytics.dim_advisor_assignment aa
          ON aa.client_key = f.client_key
         AND f.event_date BETWEEN aa.effective_from
             AND COALESCE(aa.effective_to, DATE '9999-12-31')
        WHERE aa.assignment_key IS NULL OR aa.advisor_key <> f.advisor_key
        """
    ).iloc[0, 0]
    assert int(mismatches) == 0
