"""Domain objects for deterministic Archive row reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from alma_duplicate.domain.archive import (
    ObsIdParseResult,
)
from alma_duplicate.domain.spectral import (
    FrequencySupportGrammar,
)


class ReconstructionStatus(StrEnum):
    """Outcome of reconstructing one raw Archive row."""

    LINKED = "LINKED"
    OBS_ID_UNSAFE = "OBS_ID_UNSAFE"
    MEMBER_UID_MISSING = "MEMBER_UID_MISSING"
    ASDM_UID_MISSING = "ASDM_UID_MISSING"
    PARSED_MEMBER_MISMATCH = (
        "PARSED_MEMBER_MISMATCH"
    )


class SupportMappingMethod(StrEnum):
    """Method used to map one row to one support component."""

    BRACKET_INTERVAL_CONTAINMENT = (
        "BRACKET_INTERVAL_CONTAINMENT"
    )
    BRACE_NEAREST_CENTRE = (
        "BRACE_NEAREST_CENTRE"
    )


class SupportMappingStatus(StrEnum):
    """Outcome of one SPW-to-support mapping attempt."""

    ASSIGNED = "ASSIGNED"
    RECONSTRUCTION_UNLINKED = (
        "RECONSTRUCTION_UNLINKED"
    )
    ROW_FREQUENCY_MISSING = (
        "ROW_FREQUENCY_MISSING"
    )
    UNSUPPORTED_GRAMMAR = "UNSUPPORTED_GRAMMAR"
    SUPPORT_PARSE_UNSAFE = "SUPPORT_PARSE_UNSAFE"
    NO_USABLE_COMPONENT = "NO_USABLE_COMPONENT"
    OUTSIDE_INTERVAL = "OUTSIDE_INTERVAL"
    AMBIGUOUS_MULTIPLE_INTERVALS = (
        "AMBIGUOUS_MULTIPLE_INTERVALS"
    )
    OUTSIDE_REPRESENTATION_TOLERANCE = (
        "OUTSIDE_REPRESENTATION_TOLERANCE"
    )
    AMBIGUOUS_EQUAL_DISTANCE = (
        "AMBIGUOUS_EQUAL_DISTANCE"
    )


@dataclass(frozen=True, slots=True)
class ArchiveRowInput:
    """Minimum raw row evidence required by reconstruction."""

    raw_row_id: str
    member_ous_uid: str | None
    asdm_uid: str | None
    obs_id: str | bytes | float | None
    frequency_ghz: float | None
    frequency_support: str | bytes | None


@dataclass(
    frozen=True,
    slots=True,
    order=True,
)
class SourceExecutionKey:
    """One parsed source within one Member and ASDM execution."""

    member_ous_uid: str
    asdm_uid: str
    source_name: str


@dataclass(
    frozen=True,
    slots=True,
    order=True,
)
class SourceSpwAssociationKey:
    """One observed Source-Execution-to-SPW association."""

    context: SourceExecutionKey
    spw_token: str
    spw_index: int


@dataclass(frozen=True, slots=True)
class RowReconstruction:
    """Result of linking one raw row to an association."""

    raw_row_id: str
    status: ReconstructionStatus
    obs_id_result: ObsIdParseResult
    association_key: SourceSpwAssociationKey | None
    issues: tuple[str, ...]

    @property
    def is_linked(self) -> bool:
        return (
            self.status is ReconstructionStatus.LINKED
            and self.association_key is not None
        )


@dataclass(frozen=True, slots=True)
class SupportMapping:
    """Mapping evidence between one row and one support component."""

    raw_row_id: str
    association_key: SourceSpwAssociationKey | None
    grammar_family: FrequencySupportGrammar | None
    method: SupportMappingMethod | None
    status: SupportMappingStatus
    component_index: int | None
    candidate_count: int
    frequency_difference_mhz: float | None

    @property
    def is_assigned(self) -> bool:
        return (
            self.status is SupportMappingStatus.ASSIGNED
            and self.component_index is not None
            and self.association_key is not None
        )


@dataclass(frozen=True, slots=True)
class ReconstructionBatch:
    """Canonical, order-independent reconstruction output."""

    associations: tuple[SourceSpwAssociationKey, ...]
    row_reconstructions: tuple[RowReconstruction, ...]
    support_mappings: tuple[SupportMapping, ...]

    @property
    def linked_row_count(self) -> int:
        return sum(
            reconstruction.is_linked
            for reconstruction in self.row_reconstructions
        )

    @property
    def unlinked_row_count(self) -> int:
        return (
            len(self.row_reconstructions)
            - self.linked_row_count
        )
