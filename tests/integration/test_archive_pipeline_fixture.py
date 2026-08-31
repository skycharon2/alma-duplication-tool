from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from astropy.table import Table
import pytest

from alma_duplicate.clients.archive_adapter import (
    IncompleteArchiveQueryError,
    run_archive_pipeline,
)
from alma_duplicate.clients.archive_client import (
    ArchiveClient,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryStatus,
    TapResponse,
)
from alma_duplicate.clients.archive_queries import (
    ArchiveQuerySpec,
)
from alma_duplicate.domain.normalization import (
    MissingValueStatus,
    PublisherDidMappingStatus,
    TimestampParseStatus,
)
from alma_duplicate.domain.reconstruction import (
    ReconstructionStatus,
    SupportMappingStatus,
)
from alma_duplicate.reconstruction import (
    reconstruct_archive_rows,
)
from tests.fakes import FakeTapExecutor


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "archive"
    / "archive_pipeline_v04.ecsv"
)


def _fixture_rows() -> tuple[dict[str, object], ...]:
    table = Table.read(
        FIXTURE_PATH,
        format="ascii.ecsv",
    )

    return tuple(
        {
            column: table_row[column]
            for column in table.colnames
        }
        for table_row in table
    )


def _complete_query_result():
    rows = _fixture_rows()
    declared_columns = tuple(rows[0])
    executor = FakeTapExecutor(
        [
            TapResponse(
                rows=(
                    {
                        "total_matches": len(rows),
                    },
                ),
                declared_columns=("total_matches",),
                query_status_raw="OK",
            ),
            TapResponse(
                rows=rows,
                declared_columns=declared_columns,
                query_status_raw="OK",
            ),
        ]
    )
    timestamp = datetime(
        2026,
        8,
        31,
        10,
        0,
        tzinfo=timezone.utc,
    )
    client = ArchiveClient(
        "https://example.invalid/tap",
        executor=executor,
        maxrec=100,
        clock=lambda: timestamp,
        run_id_factory=lambda: "fixture-query-run",
    )

    return client.search(
        ArchiveQuerySpec(
            ra_deg=201.365,
            dec_deg=-43.019,
            radius_deg=0.006,
        )
    )


def test_complete_fixture_runs_full_pipeline() -> None:
    query_result = _complete_query_result()
    pipeline = run_archive_pipeline(query_result)

    assert query_result.status is (
        ArchiveQueryStatus.COMPLETE
    )
    assert len(pipeline.prepared_rows) == 5
    assert pipeline.reconstruction.linked_row_count == 4
    assert pipeline.reconstruction.unlinked_row_count == 1

    observed_pairs = {
        (
            association.context.source_name,
            association.spw_index,
        )
        for association in (
            pipeline.reconstruction.associations
        )
    }

    assert ("SourceA", 0) in observed_pairs
    assert ("SourceA", 2) in observed_pairs
    assert ("SourceA", 1) not in observed_pairs

    brace_mappings = [
        mapping
        for mapping in (
            pipeline.reconstruction.support_mappings
        )
        if (
            mapping.association_key is not None
            and mapping.association_key.context.source_name
            == "SourceB"
        )
    ]

    assert len(brace_mappings) == 2
    assert {
        mapping.status
        for mapping in brace_mappings
    } == {SupportMappingStatus.ASSIGNED}
    assert {
        mapping.component_index
        for mapping in brace_mappings
    } == {1}

    unsafe_rows = [
        reconstruction
        for reconstruction in (
            pipeline.reconstruction.row_reconstructions
        )
        if reconstruction.status is (
            ReconstructionStatus.OBS_ID_UNSAFE
        )
    ]
    assert len(unsafe_rows) == 1


def test_normalization_preserves_raw_and_status() -> None:
    pipeline = run_archive_pipeline(
        _complete_query_result()
    )

    first = pipeline.prepared_rows[0]
    mismatch = pipeline.prepared_rows[2]

    assert str(first.raw_row["group_ous_uid"]).strip() == ""
    assert first.normalized_metadata.group_ous_uid.value is None
    assert (
        first.normalized_metadata.group_ous_uid.missing_status
        is MissingValueStatus.BLANK_NORMALIZED
    )
    assert (
        first.normalized_metadata.obs_release_date.status
        is TimestampParseStatus.SENTINEL_3000_DATE
    )
    assert first.normalized_metadata.obs_release_date.value is None
    assert (
        mismatch.normalized_metadata.publisher_did.status
        is PublisherDidMappingStatus.MISMATCH
    )
    assert first.raw_row_id == (
        "fixture-query-run:00000000"
    )


def test_reconstruction_remains_shuffle_invariant() -> None:
    pipeline = run_archive_pipeline(
        _complete_query_result()
    )
    reversed_inputs = tuple(
        prepared.reconstruction_input
        for prepared in reversed(
            pipeline.prepared_rows
        )
    )

    assert reconstruct_archive_rows(
        reversed_inputs
    ) == pipeline.reconstruction


@pytest.mark.parametrize(
    ("status", "error_kind"),
    [
        (ArchiveQueryStatus.OVERFLOW, None),
        (ArchiveQueryStatus.COUNT_MISMATCH, None),
        (
            ArchiveQueryStatus.ERROR,
            ArchiveQueryErrorKind.SERVICE_ERROR,
        ),
    ],
)
def test_incomplete_results_cannot_enter_pipeline(
    status: ArchiveQueryStatus,
    error_kind: ArchiveQueryErrorKind | None,
) -> None:
    complete = _complete_query_result()
    incomplete = replace(
        complete,
        status=status,
        error_kind=error_kind,
        error_message=(
            "fixture error"
            if status is ArchiveQueryStatus.ERROR
            else None
        ),
    )

    with pytest.raises(
        IncompleteArchiveQueryError,
        match="cannot enter reconstruction",
    ):
        run_archive_pipeline(incomplete)
