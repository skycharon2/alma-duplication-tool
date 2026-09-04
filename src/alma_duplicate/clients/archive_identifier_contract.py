"""Validate Archive identifier metadata independently from row grammar."""

from __future__ import annotations

import re

from alma_duplicate.clients.archive_contract import (
    TapFieldMetadata,
)
from alma_duplicate.domain.archive import (
    OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY,
    OBS_ID_WIDTH_CONTRACT_VERSION,
    ObsIdWidthContract,
    ObsIdWidthMetadataSource,
    ObsIdWidthMetadataStatus,
)

_BOUNDED_VARIABLE_ARRAYSIZE = re.compile(
    r"^(?P<maximum>[1-9][0-9]*)\*$"
)
_FIXED_ARRAYSIZE = re.compile(
    r"^(?P<maximum>[1-9][0-9]*)$"
)
_STRING_DATATYPES = frozenset(
    {
        "char",
        "unicodechar",
    }
)


def build_archive_obs_id_width_contract(
    field_metadata: tuple[TapFieldMetadata, ...],
) -> ObsIdWidthContract:
    """Interpret the response VOTable descriptor for obs_id.

    VOTable N* means a variable-length array containing at most N
    primitives, while * is unbounded. The historical truncation boundary
    is independent evidence and is never substituted for absent live
    metadata.
    """

    matches = tuple(
        field
        for field in field_metadata
        if field.name == "obs_id"
    )

    if len(matches) != 1:
        issue = (
            "obs_id_field_metadata_missing"
            if not matches
            else "obs_id_field_metadata_ambiguous"
        )
        return ObsIdWidthContract(
            raw_datatype=None,
            raw_arraysize=None,
            reported_max_length=None,
            metadata_status=(
                ObsIdWidthMetadataStatus.MISSING
                if not matches
                else ObsIdWidthMetadataStatus.INVALID
            ),
            metadata_source=(
                ObsIdWidthMetadataSource
                .RETRIEVAL_VOTABLE_FIELD
            ),
            historical_truncation_boundary=(
                OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY
            ),
            issues=(issue,),
            contract_version=OBS_ID_WIDTH_CONTRACT_VERSION,
        )

    descriptor = matches[0]
    datatype = descriptor.datatype.strip()
    arraysize = (
        descriptor.arraysize.strip()
        if descriptor.arraysize is not None
        else None
    )

    common = {
        "raw_datatype": descriptor.datatype,
        "raw_arraysize": descriptor.arraysize,
        "metadata_source": (
            ObsIdWidthMetadataSource.RETRIEVAL_VOTABLE_FIELD
        ),
        "historical_truncation_boundary": (
            OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY
        ),
        "contract_version": OBS_ID_WIDTH_CONTRACT_VERSION,
    }

    if datatype.casefold() not in _STRING_DATATYPES:
        return ObsIdWidthContract(
            **common,
            reported_max_length=None,
            metadata_status=(
                ObsIdWidthMetadataStatus
                .INCOMPATIBLE_DATATYPE
            ),
            issues=("obs_id_datatype_not_character",),
        )

    if not arraysize:
        return ObsIdWidthContract(
            **common,
            reported_max_length=None,
            metadata_status=ObsIdWidthMetadataStatus.MISSING,
            issues=("obs_id_arraysize_missing",),
        )

    if arraysize == "*":
        return ObsIdWidthContract(
            **common,
            reported_max_length=None,
            metadata_status=ObsIdWidthMetadataStatus.UNBOUNDED,
            issues=(),
        )

    bounded = _BOUNDED_VARIABLE_ARRAYSIZE.fullmatch(
        arraysize
    )
    if bounded is not None:
        return ObsIdWidthContract(
            **common,
            reported_max_length=int(
                bounded.group("maximum")
            ),
            metadata_status=(
                ObsIdWidthMetadataStatus.BOUNDED_VARIABLE
            ),
            issues=(),
        )

    fixed = _FIXED_ARRAYSIZE.fullmatch(arraysize)
    if fixed is not None:
        return ObsIdWidthContract(
            **common,
            reported_max_length=int(
                fixed.group("maximum")
            ),
            metadata_status=ObsIdWidthMetadataStatus.FIXED,
            issues=(),
        )

    return ObsIdWidthContract(
        **common,
        reported_max_length=None,
        metadata_status=ObsIdWidthMetadataStatus.INVALID,
        issues=("obs_id_arraysize_invalid",),
    )
