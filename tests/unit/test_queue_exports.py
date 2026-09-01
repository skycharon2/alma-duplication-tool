from __future__ import annotations

from alma_duplicate.clients import (
    QueueCsvClient,
    QueueCsvReadError,
    run_queue_pipeline,
)
from alma_duplicate.domain import (
    QueueCsvParseResult,
    QueueRowAssociation,
    QueueUnitInterpretation,
)
from alma_duplicate.parsers import parse_queue_csv_bytes


def test_queue_public_exports() -> None:
    assert QueueCsvClient.__name__ == "QueueCsvClient"
    assert QueueCsvReadError.__name__ == "QueueCsvReadError"
    assert QueueCsvParseResult.__name__ == "QueueCsvParseResult"
    assert QueueRowAssociation.__name__ == "QueueRowAssociation"
    assert QueueUnitInterpretation.DIRECT == "DIRECT"
    assert callable(parse_queue_csv_bytes)
    assert callable(run_queue_pipeline)
