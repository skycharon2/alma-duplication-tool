"""Gate complete Queue CSV evidence into reconstruction."""

from __future__ import annotations

from alma_duplicate.domain.queue import (
    QueueCsvParseResult,
    QueuePipelineBatch,
)
from alma_duplicate.queue_reconstruction import (
    reconstruct_queue_rows,
)

QUEUE_ADAPTER_VERSION = "1"


class IncompleteQueueCsvError(RuntimeError):
    """Raised when incomplete Queue evidence enters reconstruction."""


def run_queue_pipeline(
    result: QueueCsvParseResult,
) -> QueuePipelineBatch:
    """Reconstruct only a complete, fully adapted Queue snapshot."""

    if not result.can_reconstruct:
        raise IncompleteQueueCsvError(
            "Queue CSV status "
            f"{result.status} cannot enter reconstruction"
        )

    reconstruction = reconstruct_queue_rows(
        result.row_inputs
    )
    return QueuePipelineBatch(
        parse_result=result,
        reconstruction=reconstruction,
        adapter_version=QUEUE_ADAPTER_VERSION,
    )
