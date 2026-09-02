"""Adapt complete Archive query results into the v0.4 pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from alma_duplicate.clients.archive_contract import (
    ArchiveQueryResult,
    RawArchiveRow,
)
from alma_duplicate.clients.archive_field_contract import (
    ArchiveFieldContractValidation,
    build_archive_comparison_evidence,
    validate_archive_comparison_metadata,
)
from alma_duplicate.clients.archive_mode import (
    ArchiveSpectralAxisMetadataValidation,
    build_archive_spectral_mode_evidence,
    resolve_source_spw_spectral_modes,
    validate_archive_spectral_axis_metadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveComparisonEvidence,
    ArchiveSpectralModeEvidence,
)
from alma_duplicate.domain.normalization import (
    ArchiveMetadataInput,
    ArchiveMetadataNormalization,
)
from alma_duplicate.domain.reconstruction import (
    ArchiveRowInput,
    ReconstructionBatch,
    SourceSpwSpectralModeEvidence,
)
from alma_duplicate.normalization import (
    normalize_archive_metadata,
    normalize_optional_text,
)
from alma_duplicate.reconstruction import (
    reconstruct_archive_rows,
)

ADAPTER_VERSION = "4"


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
    comparison_evidence: ArchiveComparisonEvidence
    spectral_mode_evidence: ArchiveSpectralModeEvidence
    adapter_version: str = ADAPTER_VERSION


@dataclass(frozen=True, slots=True)
class ArchivePipelineBatch:
    """Output of the offline Archive preparation pipeline."""

    query_result: ArchiveQueryResult
    field_contract: ArchiveFieldContractValidation
    spectral_axis_contract: ArchiveSpectralAxisMetadataValidation
    prepared_rows: tuple[PreparedArchiveRow, ...]
    reconstruction: ReconstructionBatch
    source_spw_spectral_modes: tuple[
        SourceSpwSpectralModeEvidence,
        ...,
    ]
    adapter_version: str = ADAPTER_VERSION

    @property
    def comparison_units_safe(self) -> bool:
        """Return whether live units are usable for every prepared row."""

        return (
            self.field_contract.is_usable
            and all(
                prepared.comparison_evidence.unit_safe
                for prepared in self.prepared_rows
            )
        )


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


def prepare_archive_rows(
    result: ArchiveQueryResult,
    *,
    field_contract: ArchiveFieldContractValidation | None = None,
    spectral_axis_contract: (
        ArchiveSpectralAxisMetadataValidation | None
    ) = None,
) -> tuple[PreparedArchiveRow, ...]:
    """Prepare raw rows only after query completeness is established."""

    if not result.can_reconstruct:
        raise IncompleteArchiveQueryError(
            "Archive query status "
            f"{result.status} cannot enter reconstruction"
        )

    prepared_rows: list[PreparedArchiveRow] = []
    validated_fields = (
        field_contract
        if field_contract is not None
        else validate_archive_comparison_metadata(
            result.field_metadata
        )
    )
    validated_spectral_axis = (
        spectral_axis_contract
        if spectral_axis_contract is not None
        else validate_archive_spectral_axis_metadata(
            result.field_metadata
        )
    )

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

        # Keep structural absence distinct from an explicit missing value.
        _required_value(
            raw_row,
            "frequency",
            result_index=result_index,
        )
        comparison_evidence = build_archive_comparison_evidence(
            raw_row,
            validated_fields,
            query_run_id=result.provenance.query_run_id,
            raw_row_id=raw_row_id,
            result_index=result_index,
        )
        spectral_mode_evidence = (
            build_archive_spectral_mode_evidence(
                _required_value(
                    raw_row,
                    "em_xel",
                    result_index=result_index,
                ),
                validated_spectral_axis,
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
            frequency_ghz=(
                comparison_evidence
                .frequency
                .centre
                .canonical_value
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
                comparison_evidence=comparison_evidence,
                spectral_mode_evidence=spectral_mode_evidence,
            )
        )

    return tuple(prepared_rows)


def run_archive_pipeline(
    result: ArchiveQueryResult,
) -> ArchivePipelineBatch:
    """Normalize, parse, and reconstruct one complete query result."""

    field_contract = validate_archive_comparison_metadata(
        result.field_metadata
    )
    spectral_axis_contract = (
        validate_archive_spectral_axis_metadata(
            result.field_metadata
        )
    )
    prepared_rows = prepare_archive_rows(
        result,
        field_contract=field_contract,
        spectral_axis_contract=spectral_axis_contract,
    )
    reconstruction = reconstruct_archive_rows(
        prepared.reconstruction_input
        for prepared in prepared_rows
    )
    reconstructions_by_raw_row_id = {
        item.raw_row_id: item
        for item in reconstruction.row_reconstructions
    }
    linked_row_mode_evidence = []
    for prepared in prepared_rows:
        row_reconstruction = reconstructions_by_raw_row_id[
            prepared.raw_row_id
        ]
        if row_reconstruction.association_key is None:
            continue
        linked_row_mode_evidence.append(
            (
                prepared.raw_row_id,
                row_reconstruction.association_key,
                prepared.spectral_mode_evidence,
            )
        )
    source_spw_spectral_modes = resolve_source_spw_spectral_modes(
        linked_row_mode_evidence
    )

    return ArchivePipelineBatch(
        query_result=result,
        field_contract=field_contract,
        spectral_axis_contract=spectral_axis_contract,
        prepared_rows=prepared_rows,
        reconstruction=reconstruction,
        source_spw_spectral_modes=source_spw_spectral_modes,
    )
