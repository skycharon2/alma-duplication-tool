from __future__ import annotations

import pytest

from alma_duplicate.clients.archive_contract import (
    TapFieldMetadata,
)
from alma_duplicate.clients.archive_identifier_contract import (
    build_archive_obs_id_width_contract,
)
from alma_duplicate.domain.archive import (
    OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY,
    OBS_ID_WIDTH_CONTRACT_VERSION,
    ObsIdWidthContract,
    ObsIdWidthMetadataSource,
    ObsIdWidthMetadataStatus,
)


def _field(
    *,
    name: str = "obs_id",
    datatype: str = "char",
    arraysize: str | None = "64*",
) -> TapFieldMetadata:
    return TapFieldMetadata(
        name=name,
        datatype=datatype,
        arraysize=arraysize,
        unit=None,
        ucd=None,
        utype=None,
        xtype=None,
        description=None,
    )


@pytest.mark.parametrize(
    (
        "arraysize",
        "expected_status",
        "expected_maximum",
    ),
    [
        (
            "64*",
            ObsIdWidthMetadataStatus.BOUNDED_VARIABLE,
            64,
        ),
        (
            "128*",
            ObsIdWidthMetadataStatus.BOUNDED_VARIABLE,
            128,
        ),
        (
            "64",
            ObsIdWidthMetadataStatus.FIXED,
            64,
        ),
        (
            "*",
            ObsIdWidthMetadataStatus.UNBOUNDED,
            None,
        ),
        (
            None,
            ObsIdWidthMetadataStatus.MISSING,
            None,
        ),
        (
            "64x*",
            ObsIdWidthMetadataStatus.INVALID,
            None,
        ),
    ],
)
def test_build_width_contract_from_votable_arraysize(
    arraysize: str | None,
    expected_status: ObsIdWidthMetadataStatus,
    expected_maximum: int | None,
) -> None:
    contract = build_archive_obs_id_width_contract(
        (_field(arraysize=arraysize),)
    )

    assert contract.raw_arraysize == arraysize
    assert contract.reported_max_length == expected_maximum
    assert contract.metadata_status is expected_status
    assert contract.metadata_source is (
        ObsIdWidthMetadataSource.RETRIEVAL_VOTABLE_FIELD
    )
    assert contract.historical_truncation_boundary == (
        OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY
    ) == 64
    assert contract.contract_version == (
        OBS_ID_WIDTH_CONTRACT_VERSION
    ) == "1"


def test_non_character_obs_id_metadata_is_not_interpreted() -> None:
    contract = build_archive_obs_id_width_contract(
        (_field(datatype="int", arraysize=None),)
    )

    assert contract.metadata_status is (
        ObsIdWidthMetadataStatus.INCOMPATIBLE_DATATYPE
    )
    assert contract.reported_max_length is None
    assert contract.issues == (
        "obs_id_datatype_not_character",
    )


@pytest.mark.parametrize(
    ("metadata", "expected_status", "expected_issue"),
    [
        (
            (),
            ObsIdWidthMetadataStatus.MISSING,
            "obs_id_field_metadata_missing",
        ),
        (
            (_field(), _field()),
            ObsIdWidthMetadataStatus.INVALID,
            "obs_id_field_metadata_ambiguous",
        ),
    ],
)
def test_obs_id_descriptor_must_be_unique(
    metadata: tuple[TapFieldMetadata, ...],
    expected_status: ObsIdWidthMetadataStatus,
    expected_issue: str,
) -> None:
    contract = build_archive_obs_id_width_contract(metadata)

    assert contract.metadata_status is expected_status
    assert contract.issues == (expected_issue,)


def test_width_contract_rejects_inconsistent_bounded_state() -> None:
    with pytest.raises(
        ValueError,
        match="requires reported_max_length",
    ):
        ObsIdWidthContract(
            raw_datatype="char",
            raw_arraysize="64*",
            reported_max_length=None,
            metadata_status=(
                ObsIdWidthMetadataStatus.BOUNDED_VARIABLE
            ),
            metadata_source=(
                ObsIdWidthMetadataSource
                .RETRIEVAL_VOTABLE_FIELD
            ),
            historical_truncation_boundary=64,
            issues=(),
            contract_version="1",
        )
