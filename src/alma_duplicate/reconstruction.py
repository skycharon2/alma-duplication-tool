"""Deterministic reconstruction of observed ALMA Archive rows."""

from __future__ import annotations

from collections.abc import Iterable
import math

from astropy import units as u

from alma_duplicate.domain.reconstruction import (
    ArchiveRowInput,
    ReconstructionBatch,
    ReconstructionStatus,
    RowReconstruction,
    SourceExecutionKey,
    SourceSpwAssociationKey,
    SupportMapping,
    SupportMappingMethod,
    SupportMappingStatus,
)
from alma_duplicate.domain.spectral import (
    FrequencySupportComponent,
    FrequencySupportGrammar,
    ParseStatus,
)
from alma_duplicate.parsers.frequency_support import (
    parse_frequency_support,
)
from alma_duplicate.parsers.obs_id import parse_obs_id

RECONSTRUCTION_VERSION = "1"

# 04b showed that direct frequency comparisons require an
# explicit numerical tolerance.
BRACKET_INTERVAL_TOLERANCE_GHZ = 1e-9

# Used only to identify mathematically equal nearest candidates.
EQUAL_DISTANCE_TOLERANCE_MHZ = 1e-9


def _normalized_required_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _finite_frequency(
    value: float | None,
) -> float | None:
    if value is None:
        return None

    try:
        frequency = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(frequency):
        return None

    return frequency


def _reconstruct_row(
    row: ArchiveRowInput,
) -> RowReconstruction:
    obs_id_result = parse_obs_id(row.obs_id)

    if not obs_id_result.is_safe_for_reconstruction:
        return RowReconstruction(
            raw_row_id=row.raw_row_id,
            status=ReconstructionStatus.OBS_ID_UNSAFE,
            obs_id_result=obs_id_result,
            association_key=None,
            issues=tuple(
                issue.code
                for issue in obs_id_result.issues
            ),
        )

    member_ous_uid = _normalized_required_text(
        row.member_ous_uid
    )

    if member_ous_uid is None:
        return RowReconstruction(
            raw_row_id=row.raw_row_id,
            status=(
                ReconstructionStatus.MEMBER_UID_MISSING
            ),
            obs_id_result=obs_id_result,
            association_key=None,
            issues=("member_ous_uid_missing",),
        )

    asdm_uid = _normalized_required_text(
        row.asdm_uid
    )

    if asdm_uid is None:
        return RowReconstruction(
            raw_row_id=row.raw_row_id,
            status=ReconstructionStatus.ASDM_UID_MISSING,
            obs_id_result=obs_id_result,
            association_key=None,
            issues=("asdm_uid_missing",),
        )

    if (
        obs_id_result.member_ous_uid
        != member_ous_uid
    ):
        return RowReconstruction(
            raw_row_id=row.raw_row_id,
            status=(
                ReconstructionStatus
                .PARSED_MEMBER_MISMATCH
            ),
            obs_id_result=obs_id_result,
            association_key=None,
            issues=("parsed_member_uid_mismatch",),
        )

    assert obs_id_result.source_name is not None
    assert obs_id_result.spw_token is not None
    assert obs_id_result.spw_index is not None

    context = SourceExecutionKey(
        member_ous_uid=member_ous_uid,
        asdm_uid=asdm_uid,
        source_name=obs_id_result.source_name,
    )

    association = SourceSpwAssociationKey(
        context=context,
        spw_token=obs_id_result.spw_token,
        spw_index=obs_id_result.spw_index,
    )

    return RowReconstruction(
        raw_row_id=row.raw_row_id,
        status=ReconstructionStatus.LINKED,
        obs_id_result=obs_id_result,
        association_key=association,
        issues=tuple(
            issue.code
            for issue in obs_id_result.issues
        ),
    )


def _quantity_to_value(
    value: float,
    unit_text: str,
    target_unit: u.UnitBase,
) -> float | None:
    try:
        return (
            value * u.Unit(unit_text)
        ).to_value(target_unit)
    except (
        TypeError,
        ValueError,
        u.UnitConversionError,
    ):
        return None


def _map_bracket_support(
    *,
    row: ArchiveRowInput,
    reconstruction: RowReconstruction,
    components: tuple[
        FrequencySupportComponent,
        ...,
    ],
    frequency_ghz: float,
) -> SupportMapping:
    usable_components: list[
        tuple[int, float, float]
    ] = []

    for component in components:
        interval = component.frequency_interval

        if interval is None:
            continue

        low_ghz = _quantity_to_value(
            interval.low,
            interval.unit,
            u.GHz,
        )
        high_ghz = _quantity_to_value(
            interval.high,
            interval.unit,
            u.GHz,
        )

        if low_ghz is None or high_ghz is None:
            continue

        usable_components.append(
            (
                component.component_index,
                min(low_ghz, high_ghz),
                max(low_ghz, high_ghz),
            )
        )

    if not usable_components:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=(
                FrequencySupportGrammar.BRACKET
            ),
            method=(
                SupportMappingMethod
                .BRACKET_INTERVAL_CONTAINMENT
            ),
            status=(
                SupportMappingStatus.NO_USABLE_COMPONENT
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    candidates = [
        component_index
        for component_index, low_ghz, high_ghz
        in usable_components
        if (
            low_ghz
            - BRACKET_INTERVAL_TOLERANCE_GHZ
            <= frequency_ghz
            <= high_ghz
            + BRACKET_INTERVAL_TOLERANCE_GHZ
        )
    ]

    if not candidates:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=(
                FrequencySupportGrammar.BRACKET
            ),
            method=(
                SupportMappingMethod
                .BRACKET_INTERVAL_CONTAINMENT
            ),
            status=SupportMappingStatus.OUTSIDE_INTERVAL,
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    chosen_index = min(candidates)

    if len(candidates) > 1:
        status = (
            SupportMappingStatus
            .AMBIGUOUS_MULTIPLE_INTERVALS
        )
    else:
        status = SupportMappingStatus.ASSIGNED

    return SupportMapping(
        raw_row_id=row.raw_row_id,
        association_key=reconstruction.association_key,
        grammar_family=FrequencySupportGrammar.BRACKET,
        method=(
            SupportMappingMethod
            .BRACKET_INTERVAL_CONTAINMENT
        ),
        status=status,
        component_index=chosen_index,
        candidate_count=len(candidates),
        frequency_difference_mhz=None,
    )


def _brace_component_evidence(
    component: FrequencySupportComponent,
) -> tuple[int, float, float] | None:
    centre = component.displayed_center
    tolerance_mhz = (
        component.representation_tolerance_mhz
    )

    if centre is None or tolerance_mhz is None:
        return None

    centre_ghz = _quantity_to_value(
        centre.value,
        centre.unit,
        u.GHz,
    )

    if centre_ghz is None:
        return None

    return (
        component.component_index,
        centre_ghz,
        tolerance_mhz,
    )


def _map_brace_support(
    *,
    row: ArchiveRowInput,
    reconstruction: RowReconstruction,
    components: tuple[
        FrequencySupportComponent,
        ...,
    ],
    frequency_ghz: float,
) -> SupportMapping:
    usable_components = [
        evidence
        for component in components
        if (
            evidence
            := _brace_component_evidence(component)
        )
        is not None
    ]

    if not usable_components:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=FrequencySupportGrammar.BRACE,
            method=(
                SupportMappingMethod
                .BRACE_NEAREST_CENTRE
            ),
            status=(
                SupportMappingStatus.NO_USABLE_COMPONENT
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    differences = [
        (
            component_index,
            abs(centre_ghz - frequency_ghz) * 1e3,
            tolerance_mhz,
        )
        for (
            component_index,
            centre_ghz,
            tolerance_mhz,
        ) in usable_components
    ]

    minimum_difference_mhz = min(
        difference_mhz
        for _, difference_mhz, _ in differences
    )

    nearest = sorted(
        (
            component_index,
            difference_mhz,
            tolerance_mhz,
        )
        for (
            component_index,
            difference_mhz,
            tolerance_mhz,
        ) in differences
        if math.isclose(
            difference_mhz,
            minimum_difference_mhz,
            rel_tol=0.0,
            abs_tol=EQUAL_DISTANCE_TOLERANCE_MHZ,
        )
    )

    chosen_index, chosen_difference, tolerance = (
        nearest[0]
    )

    if len(nearest) > 1:
        status = (
            SupportMappingStatus
            .AMBIGUOUS_EQUAL_DISTANCE
        )
    elif chosen_difference <= tolerance:
        status = SupportMappingStatus.ASSIGNED
    else:
        status = (
            SupportMappingStatus
            .OUTSIDE_REPRESENTATION_TOLERANCE
        )

    return SupportMapping(
        raw_row_id=row.raw_row_id,
        association_key=reconstruction.association_key,
        grammar_family=FrequencySupportGrammar.BRACE,
        method=(
            SupportMappingMethod
            .BRACE_NEAREST_CENTRE
        ),
        status=status,
        component_index=chosen_index,
        candidate_count=len(nearest),
        frequency_difference_mhz=chosen_difference,
    )


def _map_support(
    row: ArchiveRowInput,
    reconstruction: RowReconstruction,
) -> SupportMapping:
    if not reconstruction.is_linked:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=None,
            grammar_family=None,
            method=None,
            status=(
                SupportMappingStatus
                .RECONSTRUCTION_UNLINKED
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    support_result = parse_frequency_support(
        row.frequency_support
    )

    if support_result.grammar_family not in {
        FrequencySupportGrammar.BRACKET,
        FrequencySupportGrammar.BRACE,
    }:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=(
                support_result.grammar_family
            ),
            method=None,
            status=(
                SupportMappingStatus.UNSUPPORTED_GRAMMAR
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    if (
        support_result.parse_status
        is not ParseStatus.PARSED
        or not support_result.is_valid
    ):
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=(
                support_result.grammar_family
            ),
            method=None,
            status=(
                SupportMappingStatus.SUPPORT_PARSE_UNSAFE
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    frequency_ghz = _finite_frequency(
        row.frequency_ghz
    )

    if frequency_ghz is None:
        return SupportMapping(
            raw_row_id=row.raw_row_id,
            association_key=(
                reconstruction.association_key
            ),
            grammar_family=(
                support_result.grammar_family
            ),
            method=None,
            status=(
                SupportMappingStatus.ROW_FREQUENCY_MISSING
            ),
            component_index=None,
            candidate_count=0,
            frequency_difference_mhz=None,
        )

    if (
        support_result.grammar_family
        is FrequencySupportGrammar.BRACKET
    ):
        return _map_bracket_support(
            row=row,
            reconstruction=reconstruction,
            components=support_result.components,
            frequency_ghz=frequency_ghz,
        )

    return _map_brace_support(
        row=row,
        reconstruction=reconstruction,
        components=support_result.components,
        frequency_ghz=frequency_ghz,
    )


def reconstruct_archive_rows(
    rows: Iterable[ArchiveRowInput],
) -> ReconstructionBatch:
    """Reconstruct only associations observed in supplied rows.

    The result is canonicalized by raw_row_id so input ordering
    cannot change the returned batch.
    """

    input_rows = tuple(rows)

    raw_row_ids = [
        row.raw_row_id
        for row in input_rows
    ]

    if any(
        not str(raw_row_id).strip()
        for raw_row_id in raw_row_ids
    ):
        raise ValueError(
            "Every Archive row requires a non-blank raw_row_id"
        )

    if len(raw_row_ids) != len(set(raw_row_ids)):
        raise ValueError(
            "raw_row_id values must be unique"
        )

    ordered_rows = tuple(
        sorted(
            input_rows,
            key=lambda row: row.raw_row_id,
        )
    )

    row_reconstructions: list[
        RowReconstruction
    ] = []
    support_mappings: list[SupportMapping] = []
    associations: set[
        SourceSpwAssociationKey
    ] = set()

    for row in ordered_rows:
        reconstruction = _reconstruct_row(row)
        mapping = _map_support(
            row,
            reconstruction,
        )

        row_reconstructions.append(
            reconstruction
        )
        support_mappings.append(mapping)

        if reconstruction.association_key is not None:
            associations.add(
                reconstruction.association_key
            )

    return ReconstructionBatch(
        associations=tuple(sorted(associations)),
        row_reconstructions=tuple(
            row_reconstructions
        ),
        support_mappings=tuple(
            support_mappings
        ),
    )
