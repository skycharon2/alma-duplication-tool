from __future__ import annotations

import random

import pytest

from alma_duplicate.domain.reconstruction import (
    ArchiveRowInput,
    ReconstructionStatus,
    SupportMappingStatus,
)
from alma_duplicate.reconstruction import (
    reconstruct_archive_rows,
)

MEMBER_UID = "uid://A001/X3955/X44"
ASDM_UID = "uid://A002/X123/X456"


def _bracket_support(
    low: float,
    high: float,
) -> str:
    return (
        f"[{low:.3f}..{high:.3f}GHz, "
        "1MHz, "
        "1mJy/beam@10km/s, "
        "0.2mJy/beam@native, XX YY]"
    )


def _brace_component(
    centre: float,
) -> str:
    return (
        f"{{{centre:.2f}GHz,2000000.00kHz,"
        "20.8mJy/beam@10km/s,"
        "1.3mJy/beam@native, XX YY}"
    )


def _row(
    *,
    raw_row_id: str,
    source: str,
    spw: int,
    frequency_ghz: float | None,
    frequency_support: str | None,
    member_ous_uid: str | None = MEMBER_UID,
    asdm_uid: str | None = ASDM_UID,
    obs_id: str | None = None,
) -> ArchiveRowInput:
    if obs_id is None:
        obs_id = (
            f"{MEMBER_UID}.source."
            f"{source}.spw.{spw}"
        )

    return ArchiveRowInput(
        raw_row_id=raw_row_id,
        member_ous_uid=member_ous_uid,
        asdm_uid=asdm_uid,
        obs_id=obs_id,
        frequency_ghz=frequency_ghz,
        frequency_support=frequency_support,
    )


def test_sparse_source_spw_associations_are_preserved() -> None:
    rows = []

    for spw in range(7):
        frequency = 100.0 + spw
        rows.append(
            _row(
                raw_row_id=f"full-{spw}",
                source="Moon_full",
                spw=spw,
                frequency_ghz=frequency,
                frequency_support=_bracket_support(
                    frequency - 0.1,
                    frequency + 0.1,
                ),
            )
        )

    for spw in range(4):
        frequency = 100.0 + spw
        rows.append(
            _row(
                raw_row_id=f"reg-{spw}",
                source="Moon_reg",
                spw=spw,
                frequency_ghz=frequency,
                frequency_support=_bracket_support(
                    frequency - 0.1,
                    frequency + 0.1,
                ),
            )
        )

    result = reconstruct_archive_rows(rows)

    observed_pairs = {
        (
            association.context.source_name,
            association.spw_index,
        )
        for association in result.associations
    }

    assert len(result.associations) == 11
    assert result.linked_row_count == 11
    assert result.unlinked_row_count == 0

    assert {
        ("Moon_full", spw)
        for spw in range(7)
    }.issubset(observed_pairs)

    assert {
        ("Moon_reg", spw)
        for spw in range(4)
    }.issubset(observed_pairs)

    # These Cartesian-product rows must not be invented.
    assert ("Moon_reg", 4) not in observed_pairs
    assert ("Moon_reg", 5) not in observed_pairs
    assert ("Moon_reg", 6) not in observed_pairs

    assert len(result.associations) != 2 * 7


def test_multiple_rows_may_support_one_association() -> None:
    support = _bracket_support(99.0, 101.0)

    rows = [
        _row(
            raw_row_id="row-a",
            source="Target",
            spw=0,
            frequency_ghz=100.0,
            frequency_support=support,
        ),
        _row(
            raw_row_id="row-b",
            source="Target",
            spw=0,
            frequency_ghz=100.0,
            frequency_support=support,
        ),
    ]

    result = reconstruct_archive_rows(rows)

    assert len(result.row_reconstructions) == 2
    assert result.linked_row_count == 2
    assert result.unlinked_row_count == 0

    # Multiple raw rows may support one logical association.
    assert len(result.associations) == 1


def test_width_boundary_obs_id_is_not_linked() -> None:
    width_boundary_obs_id = (
        "uid://A001/X1/X1.source."
        "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS"
        ".spw.12"
    )

    assert len(width_boundary_obs_id) == 64

    row = _row(
        raw_row_id="width-risk",
        source="ignored",
        spw=12,
        frequency_ghz=100.0,
        frequency_support=_bracket_support(
            99.0,
            101.0,
        ),
        member_ous_uid="uid://A001/X1/X1",
        obs_id=width_boundary_obs_id,
    )

    result = reconstruct_archive_rows([row])

    reconstruction = result.row_reconstructions[0]
    mapping = result.support_mappings[0]

    assert (
        reconstruction.status
        is ReconstructionStatus.OBS_ID_UNSAFE
    )
    assert not reconstruction.is_linked
    assert result.linked_row_count == 0
    assert result.unlinked_row_count == 1
    assert result.associations == ()

    assert (
        mapping.status
        is SupportMappingStatus.RECONSTRUCTION_UNLINKED
    )
    assert mapping.association_key is None
    assert mapping.component_index is None


def test_member_uid_mismatch_is_not_linked() -> None:
    row = _row(
        raw_row_id="member-mismatch",
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support=_bracket_support(
            99.0,
            101.0,
        ),
        member_ous_uid=(
            "uid://A001/DIFFERENT/X1"
        ),
    )

    result = reconstruct_archive_rows([row])
    reconstruction = result.row_reconstructions[0]

    assert (
        reconstruction.status
        is ReconstructionStatus.PARSED_MEMBER_MISMATCH
    )
    assert not reconstruction.is_linked
    assert result.associations == ()
    assert (
        "parsed_member_uid_mismatch"
        in reconstruction.issues
    )


def test_missing_member_uid_is_not_linked() -> None:
    row = _row(
        raw_row_id="missing-member",
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support=_bracket_support(
            99.0,
            101.0,
        ),
        member_ous_uid=None,
    )

    result = reconstruct_archive_rows([row])

    assert (
        result.row_reconstructions[0].status
        is ReconstructionStatus.MEMBER_UID_MISSING
    )
    assert result.associations == ()


def test_missing_asdm_uid_is_not_linked() -> None:
    row = _row(
        raw_row_id="missing-asdm",
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support=_bracket_support(
            99.0,
            101.0,
        ),
        asdm_uid="",
    )

    result = reconstruct_archive_rows([row])

    assert (
        result.row_reconstructions[0].status
        is ReconstructionStatus.ASDM_UID_MISSING
    )
    assert result.associations == ()


def test_bracket_interval_mapping() -> None:
    support = (
        _bracket_support(100.0, 101.0)
        + " U "
        + _bracket_support(110.0, 111.0)
    )

    rows = [
        _row(
            raw_row_id="spw-0",
            source="Target",
            spw=0,
            frequency_ghz=100.5,
            frequency_support=support,
        ),
        _row(
            raw_row_id="spw-1",
            source="Target",
            spw=1,
            frequency_ghz=110.5,
            frequency_support=support,
        ),
    ]

    result = reconstruct_archive_rows(rows)

    mapping_by_row = {
        mapping.raw_row_id: mapping
        for mapping in result.support_mappings
    }

    first = mapping_by_row["spw-0"]
    second = mapping_by_row["spw-1"]

    assert (
        first.status
        is SupportMappingStatus.ASSIGNED
    )
    assert first.component_index == 1
    assert first.candidate_count == 1

    assert (
        second.status
        is SupportMappingStatus.ASSIGNED
    )
    assert second.component_index == 2
    assert second.candidate_count == 1


def test_overlapping_bracket_intervals_are_ambiguous() -> None:
    support = (
        _bracket_support(100.0, 102.0)
        + " U "
        + _bracket_support(101.0, 103.0)
    )

    row = _row(
        raw_row_id="overlap",
        source="Target",
        spw=0,
        frequency_ghz=101.5,
        frequency_support=support,
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .AMBIGUOUS_MULTIPLE_INTERVALS
    )
    assert mapping.candidate_count == 2
    assert mapping.component_index == 1


def test_frequency_outside_bracket_intervals_is_reported() -> None:
    support = (
        _bracket_support(100.0, 101.0)
        + " U "
        + _bracket_support(110.0, 111.0)
    )

    row = _row(
        raw_row_id="outside-bracket",
        source="Target",
        spw=0,
        frequency_ghz=105.0,
        frequency_support=support,
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus.OUTSIDE_INTERVAL
    )
    assert mapping.component_index is None
    assert mapping.candidate_count == 0


def test_brace_mapping_allows_many_to_one() -> None:
    support = " U ".join(
        [
            _brace_component(229.98),
            _brace_component(231.98),
            _brace_component(245.98),
            _brace_component(247.98),
        ]
    )

    rows = [
        _row(
            raw_row_id="spw-0",
            source="Moon_full",
            spw=0,
            frequency_ghz=229.981382,
            frequency_support=support,
        ),
        _row(
            raw_row_id="spw-4",
            source="Moon_full",
            spw=4,
            frequency_ghz=229.978618,
            frequency_support=support,
        ),
    ]

    result = reconstruct_archive_rows(rows)

    assert len(result.associations) == 2
    assert len(result.support_mappings) == 2

    assert all(
        mapping.status
        is SupportMappingStatus.ASSIGNED
        for mapping in result.support_mappings
    )

    # Two distinct SPWs map to the same brace component.
    assert {
        mapping.component_index
        for mapping in result.support_mappings
    } == {1}

    assert all(
        mapping.frequency_difference_mhz
        == pytest.approx(1.382)
        for mapping in result.support_mappings
    )


def test_brace_mapping_outside_tolerance_is_reported() -> None:
    row = _row(
        raw_row_id="outside-brace",
        source="Target",
        spw=0,
        frequency_ghz=100.02,
        frequency_support=_brace_component(100.00),
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .OUTSIDE_REPRESENTATION_TOLERANCE
    )

    # The nearest component is retained as diagnostic evidence,
    # but status is not ASSIGNED.
    assert mapping.component_index == 1
    assert (
        mapping.frequency_difference_mhz
        == pytest.approx(20.0)
    )
    assert not mapping.is_assigned


def test_equal_distance_brace_mapping_is_ambiguous() -> None:
    support = (
        _brace_component(100.00)
        + " U "
        + _brace_component(100.02)
    )

    row = _row(
        raw_row_id="equal-distance",
        source="Target",
        spw=0,
        frequency_ghz=100.01,
        frequency_support=support,
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .AMBIGUOUS_EQUAL_DISTANCE
    )
    assert mapping.candidate_count == 2

    # Lowest component index is retained deterministically,
    # but the mapping is not considered assigned.
    assert mapping.component_index == 1
    assert not mapping.is_assigned


def test_missing_row_frequency_is_reported() -> None:
    row = _row(
        raw_row_id="missing-frequency",
        source="Target",
        spw=0,
        frequency_ghz=None,
        frequency_support=_bracket_support(
            100.0,
            101.0,
        ),
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .ROW_FREQUENCY_MISSING
    )
    assert mapping.component_index is None


def test_missing_frequency_support_is_reported() -> None:
    row = _row(
        raw_row_id="missing-support",
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support=None,
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .UNSUPPORTED_GRAMMAR
    )
    assert mapping.component_index is None


def test_malformed_frequency_support_is_unsafe() -> None:
    row = _row(
        raw_row_id="malformed-support",
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support="[malformed]",
    )

    mapping = reconstruct_archive_rows(
        [row]
    ).support_mappings[0]

    assert (
        mapping.status
        is SupportMappingStatus
        .SUPPORT_PARSE_UNSAFE
    )
    assert mapping.component_index is None


def test_reconstruction_is_shuffle_invariant() -> None:
    rows = [
        _row(
            raw_row_id=f"row-{index:02d}",
            source=(
                "Source_A"
                if index % 2 == 0
                else "Source_B"
            ),
            spw=index % 4,
            frequency_ghz=100.0 + index,
            frequency_support=_bracket_support(
                99.9 + index,
                100.1 + index,
            ),
        )
        for index in range(12)
    ]

    baseline = reconstruct_archive_rows(rows)

    for seed in [0, 1, 7, 42, 2026]:
        shuffled = rows.copy()
        random.Random(seed).shuffle(shuffled)

        reconstructed = reconstruct_archive_rows(
            shuffled
        )

        assert reconstructed == baseline


def test_duplicate_raw_row_id_is_rejected() -> None:
    rows = [
        _row(
            raw_row_id="duplicate",
            source="Source_A",
            spw=0,
            frequency_ghz=100.0,
            frequency_support=_bracket_support(
                99.0,
                101.0,
            ),
        ),
        _row(
            raw_row_id="duplicate",
            source="Source_B",
            spw=1,
            frequency_ghz=101.0,
            frequency_support=_bracket_support(
                100.0,
                102.0,
            ),
        ),
    ]

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        reconstruct_archive_rows(rows)


@pytest.mark.parametrize(
    "raw_row_id",
    ["", "   "],
)
def test_blank_raw_row_id_is_rejected(
    raw_row_id: str,
) -> None:
    row = _row(
        raw_row_id=raw_row_id,
        source="Target",
        spw=0,
        frequency_ghz=100.0,
        frequency_support=_bracket_support(
            99.0,
            101.0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="non-blank",
    ):
        reconstruct_archive_rows([row])