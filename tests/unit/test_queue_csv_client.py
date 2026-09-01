from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alma_duplicate.clients.queue_csv_adapter import (
    IncompleteQueueCsvError,
    run_queue_pipeline,
)
from alma_duplicate.clients.queue_csv_client import (
    QueueCsvClient,
    QueueCsvReadError,
)
from alma_duplicate.domain.queue import QueueParseStatus

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "queue"
    / "queue_pipeline_v1.csv"
)


def test_client_records_capture_provenance() -> None:
    captured_at = datetime(
        2026,
        9,
        1,
        10,
        30,
        tzinfo=UTC,
    )
    client = QueueCsvClient(
        "https://example.invalid/queue.csv",
        clock=lambda: captured_at,
    )

    result = client.load(FIXTURE_PATH)

    assert result.is_complete
    assert result.snapshot.source_url == (
        "https://example.invalid/queue.csv"
    )
    assert result.snapshot.captured_at == captured_at
    assert result.snapshot.byte_length == FIXTURE_PATH.stat().st_size


def test_client_read_failure_is_typed(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"

    with pytest.raises(QueueCsvReadError):
        QueueCsvClient().load(missing)


def test_complete_result_runs_pipeline() -> None:
    result = QueueCsvClient().load(FIXTURE_PATH)

    pipeline = run_queue_pipeline(result)

    assert pipeline.parse_result is result
    assert len(pipeline.reconstruction.associations) == 13
    assert pipeline.reconstruction.sparse_group_count == 2


def test_incomplete_result_cannot_enter_reconstruction() -> None:
    result = QueueCsvClient().load(FIXTURE_PATH)
    incomplete = replace(result, status=QueueParseStatus.ERROR)

    with pytest.raises(IncompleteQueueCsvError):
        run_queue_pipeline(incomplete)
