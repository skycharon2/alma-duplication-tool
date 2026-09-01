from __future__ import annotations

from pathlib import Path

from alma_duplicate.clients.queue_csv_adapter import run_queue_pipeline
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.domain.queue import (
    QueueIssueKind,
    QueueParseStatus,
    RegularSpwEvidence,
    SpectralScanEvidence,
)

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "queue"
    / "queue_pipeline_v1.csv"
)


def test_queue_fixture_runs_complete_pipeline() -> None:
    result = QueueCsvClient().load(FIXTURE_PATH)
    pipeline = run_queue_pipeline(result)

    assert result.status is QueueParseStatus.COMPLETE_WITH_WARNINGS
    assert [issue.kind for issue in result.issues] == [
        QueueIssueKind.CONFLICTING_UNIT_DECLARATION
    ]
    assert len(result.raw_rows) == len(result.row_inputs) == 13
    assert len(result.field_metadata) == 79
    assert sum(
        isinstance(row.spectral, RegularSpwEvidence)
        for row in result.row_inputs
    ) == 12
    assert sum(
        isinstance(row.spectral, SpectralScanEvidence)
        for row in result.row_inputs
    ) == 1
    assert sum(
        len(row.spectral.spws)
        for row in result.row_inputs
        if isinstance(row.spectral, RegularSpwEvidence)
    ) == 69

    reconstruction = pipeline.reconstruction
    assert len(reconstruction.associations) == 13
    assert len(reconstruction.factorization) == 6
    assert reconstruction.sparse_group_count == 2
    assert sum(
        item.repeated_association_count
        for item in reconstruction.factorization
    ) == 1
