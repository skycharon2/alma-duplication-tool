"""Minimal opt-in smoke test for the production ALMA TAP boundary."""

from __future__ import annotations

import os

import pytest

from alma_duplicate.clients import (
    ARCHIVE_SCHEMA_VERSION,
    ArchiveClient,
    ArchiveQuerySpec,
    ArchiveQueryStatus,
)


pytestmark = pytest.mark.live

DEFAULT_ALMA_TAP_ENDPOINT = (
    "https://almascience.eso.org/tap"
)
LIVE_MAXREC = 500

EXECUTED_STATUSES = frozenset(
    {
        ArchiveQueryStatus.COMPLETE,
        ArchiveQueryStatus.OVERFLOW,
        ArchiveQueryStatus.COUNT_MISMATCH,
    }
)


def test_live_archive_tap_contract() -> None:
    """Verify execution, declared schema, and query provenance."""

    endpoint = os.environ.get(
        "ALMA_TAP_ENDPOINT",
        DEFAULT_ALMA_TAP_ENDPOINT,
    )
    client = ArchiveClient(
        endpoint,
        maxrec=LIVE_MAXREC,
    )

    # Supervisor CASE1 position, searched with a deliberately small radius.
    # Archive contents may change, so no project ID or fixed row count is
    # asserted here.
    result = client.search(
        ArchiveQuerySpec(
            ra_deg=278.4163333333333,
            dec_deg=-21.0610833333333,
            radius_deg=1.0 / 3600.0,
        )
    )
    provenance = result.provenance

    print(
        "\nLive Archive TAP smoke result:"
        f"\n  endpoint={provenance.endpoint}"
        f"\n  status={result.status}"
        f"\n  expected_count={provenance.expected_count}"
        f"\n  retrieved_count={provenance.retrieved_count}"
        f"\n  count_status={provenance.count_query_status_raw}"
        f"\n  retrieval_status="
        f"{provenance.retrieval_query_status_raw}"
        f"\n  query_run_id={provenance.query_run_id}"
        f"\n  query_hash={provenance.query_hash}"
    )

    if result.status is ArchiveQueryStatus.ERROR:
        pytest.fail(
            "Live Archive TAP request returned ERROR: "
            f"{result.error_kind}: {result.error_message}"
        )

    assert result.status in EXECUTED_STATUSES
    assert result.error_kind is None
    assert result.error_message is None
    assert result.missing_columns == ()

    assert provenance.endpoint == endpoint.strip().rstrip("/")
    assert provenance.query_run_id.strip()
    assert provenance.count_adql.startswith("SELECT COUNT(*)")
    assert provenance.retrieval_adql.startswith("SELECT\n")
    assert provenance.configured_maxrec == LIVE_MAXREC
    assert provenance.expected_count is not None
    assert provenance.expected_count >= 0
    assert provenance.retrieved_count == len(result.rows)
    assert provenance.count_query_status_raw == "OK"
    assert provenance.retrieval_query_status_raw in {
        "OK",
        "OVERFLOW",
    }
    assert provenance.finished_at is not None
    assert provenance.finished_at >= provenance.started_at
    assert provenance.client_version.strip()
    assert provenance.schema_version == ARCHIVE_SCHEMA_VERSION
    assert len(provenance.query_hash) == 64
    assert all(
        character in "0123456789abcdef"
        for character in provenance.query_hash
    )
