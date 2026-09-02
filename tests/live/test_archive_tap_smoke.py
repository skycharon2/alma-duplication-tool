"""Minimal opt-in smoke test for the production ALMA TAP boundary."""

from __future__ import annotations

import os

import pytest

from alma_duplicate.clients import (
    ARCHIVE_SCHEMA_VERSION,
    ARCHIVE_SELECTED_COLUMNS,
    ArchiveClient,
    ArchiveFrequencyPrefilterStatus,
    ArchiveQuerySpec,
    ArchiveQueryStatus,
    ArchiveQueryResult,
    run_archive_pipeline,
)


pytestmark = pytest.mark.live

DEFAULT_ALMA_TAP_ENDPOINT = (
    "https://almascience.eso.org/tap"
)
LIVE_MAXREC = 5000

EXECUTED_STATUSES = frozenset(
    {
        ArchiveQueryStatus.COMPLETE,
        ArchiveQueryStatus.OVERFLOW,
        ArchiveQueryStatus.COUNT_MISMATCH,
    }
)


@pytest.fixture(scope="module")
def live_archive_result() -> ArchiveQueryResult:
    """Execute one live request shared by all live smoke tests."""

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
    return client.search(
        ArchiveQuerySpec(
            ra_deg=278.4163333333333,
            dec_deg=-21.0610833333333,
            radius_deg=1.0 / 3600.0,
        )
    )


def test_live_archive_tap_contract(
    live_archive_result: ArchiveQueryResult,
) -> None:
    """Verify execution, declared schema, and query provenance."""

    result = live_archive_result
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
        f"\n  field_metadata={len(result.field_metadata)}"
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
    assert tuple(
        field.name
        for field in result.field_metadata
    ) == ARCHIVE_SELECTED_COLUMNS
    assert all(
        field.datatype.strip()
        for field in result.field_metadata
    )

    expected_endpoint = os.environ.get(
        "ALMA_TAP_ENDPOINT",
        DEFAULT_ALMA_TAP_ENDPOINT,
    ).strip().rstrip("/")

    assert provenance.endpoint == expected_endpoint
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


def test_live_archive_pipeline_contract(
    live_archive_result: ArchiveQueryResult,
) -> None:
    """Run one complete live result through reconstruction."""

    result = live_archive_result

    assert result.status is ArchiveQueryStatus.COMPLETE, (
        "The selected live closure query must be complete before "
        "its rows enter reconstruction. "
        f"Observed status: {result.status}"
    )

    assert result.rows, (
        "The live closure coordinate returned no rows, so the "
        "normalization/parsing/reconstruction path was not exercised."
    )

    pipeline = run_archive_pipeline(result)
    reconstruction = pipeline.reconstruction

    assert pipeline.query_result is result
    assert pipeline.field_contract.is_usable, (
        "Live Archive comparison-field metadata drifted: "
        f"{pipeline.field_contract.unusable_fields}"
    )
    assert pipeline.comparison_units_safe

    assert len(pipeline.prepared_rows) == len(result.rows)

    assert (
        len(reconstruction.row_reconstructions)
        == len(result.rows)
    )

    assert (
        reconstruction.linked_row_count
        + reconstruction.unlinked_row_count
        == len(result.rows)
    )

    raw_row_ids = tuple(
        prepared.raw_row_id
        for prepared in pipeline.prepared_rows
    )

    assert len(set(raw_row_ids)) == len(raw_row_ids)

    for prepared in pipeline.prepared_rows:
        assert (
            prepared.raw_row
            == result.rows[prepared.result_index]
        )

    assert reconstruction.linked_row_count > 0
    assert reconstruction.associations

    print(
        "\nLive Archive pipeline result:"
        f"\n  retrieved_rows={len(result.rows)}"
        f"\n  prepared_rows={len(pipeline.prepared_rows)}"
        f"\n  linked_rows={reconstruction.linked_row_count}"
        f"\n  unlinked_rows={reconstruction.unlinked_row_count}"
        f"\n  associations={len(reconstruction.associations)}"
        f"\n  support_mappings="
        f"{len(reconstruction.support_mappings)}"
    )


def test_live_frequency_prefilter_is_unit_gated() -> None:
    """Exercise TAP_SCHEMA verification before Archive unit arithmetic."""

    endpoint = os.environ.get(
        "ALMA_TAP_ENDPOINT",
        DEFAULT_ALMA_TAP_ENDPOINT,
    )
    result = ArchiveClient(endpoint, maxrec=LIVE_MAXREC).search(
        ArchiveQuerySpec(
            ra_deg=278.4163333333333,
            dec_deg=-21.0610833333333,
            radius_deg=1.0 / 3600.0,
            frequency_min_ghz=1.0,
            frequency_max_ghz=1000.0,
        )
    )

    assert result.status in EXECUTED_STATUSES
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.VERIFIED_EXACT_UNITS
    )
    assert len(result.provenance.query_unit_metadata) == 2
    assert "bandwidth / 1000000000.0" in (
        result.provenance.count_adql
    )
