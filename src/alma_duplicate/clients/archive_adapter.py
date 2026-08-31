"""Adapt complete Archive query results into the v0.4 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import math

from alma_duplicate.clients.archive_contract import (
    ArchiveQueryResult,
    RawArchiveRow,
)
from alma_duplicate.domain.normalization import (
    ArchiveMetadataInput,
    ArchiveMetadataNormalization,
)
from alma_duplicate.domain.reconstruction import (
    ArchiveRowInput,
    ReconstructionBatch,
)
from alma_duplicate.normalization import (
    normalize_archive_metadata,
    normalize_optional_text,
)
from alma_duplicate.reconstruction import (
    reconstruct_archive_rows,
)


ADAPTER_VERSION = "1"


class IncompleteArchiveQueryError(RuntimeError):
    """Raised when incomplete TAP evidence enters reconstruction."""


class ArchiveRowAdapterError(ValueError):
    """Raised when a declared row cannot satisfy the adapter contract."""


@dataclass(frozen=True, slots=True)
class PreparedArchiveRow:
    """Raw evidence plus normalized and reconstruction-ready projections."""

    raw_row_id: str
    result_index: int
    raw_row: RawArchiveRow
    normalized_metadata: ArchiveMetadataNormalization
    reconstruction_input: ArchiveRowInput
    adapter_version: str = ADAPTER_VERSION


@dataclass(frozen=True, slots=True)
class ArchivePipelineBatch:
    """Output of the offline Archive preparation pipeline."""

    query_result: ArchiveQueryResult
    prepared_rows: tuple[PreparedArchiveRow, ...]
    reconstruction: ReconstructionBatch
    adapter_version: str = ADAPTER_VERSION


def _required_value(
    row: RawArchiveRow,
    column: str,
    *,
    result_index: int,
) -> object:
    try:
        return row[column]
    except KeyError as exc:
        raise ArchiveRowAdapterError(
            "Archive row "
            f"{result_index} is missing declared column "
            f"{column!r}"
        ) from exc


def _optional_text(value: object) -> str | None:
    return normalize_optional_text(value).value


def _optional_finite_float(
    value: object,
) -> float | None:
    mask = getattr(value, "mask", False)
    try:
        if bool(mask):
            return None
    except (TypeError, ValueError):
        raise ArchiveRowAdapterError(
            "Archive adapter expects scalar values"
        ) from None

    if value is None:
        return None

    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(converted):
        return None

    return converted


def prepare_archive_rows(
    result: ArchiveQueryResult,
) -> tuple[PreparedArchiveRow, ...]:
    """Prepare raw rows only after query completeness is established."""

    if not result.can_reconstruct:
        raise IncompleteArchiveQueryError(
            "Archive query status "
            f"{result.status} cannot enter reconstruction"
        )

    prepared_rows: list[PreparedArchiveRow] = []

    for result_index, raw_row in enumerate(result.rows):
        raw_row_id = (
            f"{result.provenance.query_run_id}:"
            f"{result_index:08d}"
        )

        normalized_metadata = normalize_archive_metadata(
            ArchiveMetadataInput(
                proposal_id=_required_value(
                    raw_row,
                    "proposal_id",
                    result_index=result_index,
                ),
                obs_publisher_did=_required_value(
                    raw_row,
                    "obs_publisher_did",
                    result_index=result_index,
                ),
                group_ous_uid=_required_value(
                    raw_row,
                    "group_ous_uid",
                    result_index=result_index,
                ),
                science_observation=_required_value(
                    raw_row,
                    "science_observation",
                    result_index=result_index,
                ),
                is_mosaic=_required_value(
                    raw_row,
                    "is_mosaic",
                    result_index=result_index,
                ),
                qa2_passed=_required_value(
                    raw_row,
                    "qa2_passed",
                    result_index=result_index,
                ),
                obs_release_date=_required_value(
                    raw_row,
                    "obs_release_date",
                    result_index=result_index,
                ),
                last_modified=_required_value(
                    raw_row,
                    "lastModified",
                    result_index=result_index,
                ),
            )
        )

        reconstruction_input = ArchiveRowInput(
            raw_row_id=raw_row_id,
            member_ous_uid=_optional_text(
                _required_value(
                    raw_row,
                    "member_ous_uid",
                    result_index=result_index,
                )
            ),
            asdm_uid=_optional_text(
                _required_value(
                    raw_row,
                    "asdm_uid",
                    result_index=result_index,
                )
            ),
            obs_id=_optional_text(
                _required_value(
                    raw_row,
                    "obs_id",
                    result_index=result_index,
                )
            ),
            frequency_ghz=_optional_finite_float(
                _required_value(
                    raw_row,
                    "frequency",
                    result_index=result_index,
                )
            ),
            frequency_support=_optional_text(
                _required_value(
                    raw_row,
                    "frequency_support",
                    result_index=result_index,
                )
            ),
        )

        prepared_rows.append(
            PreparedArchiveRow(
                raw_row_id=raw_row_id,
                result_index=result_index,
                raw_row=raw_row,
                normalized_metadata=normalized_metadata,
                reconstruction_input=reconstruction_input,
            )
        )

    return tuple(prepared_rows)


def run_archive_pipeline(
    result: ArchiveQueryResult,
) -> ArchivePipelineBatch:
    """Normalize, parse, and reconstruct one complete query result."""

    prepared_rows = prepare_archive_rows(result)
    reconstruction = reconstruct_archive_rows(
        prepared.reconstruction_input
        for prepared in prepared_rows
    )

    return ArchivePipelineBatch(
        query_result=result,
        prepared_rows=prepared_rows,
        reconstruction=reconstruction,
    )
