"""Explicit Portal blank-Mosaic interpretation, separate from raw parsing."""

from alma_duplicate.domain.queue import QueueMosaicKind

DECISION_REF = "docs/queue_blank_mosaic.md"


def uses_blank_mosaic_interpretation(row):
    """Only promote the parser's blank-with-offset category, never arbitrary gaps."""
    return (
        row.spatial.mosaic_kind is QueueMosaicKind.UNSPECIFIED_WITH_OFFSET
        and row.raw_row.value("Mosaic").strip() == ""
    )


def is_queue_single_point(row):
    return (row.spatial.mosaic_kind is QueueMosaicKind.SINGLE_FIELD
            or uses_blank_mosaic_interpretation(row))
