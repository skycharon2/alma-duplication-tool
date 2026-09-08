"""Source-bound spatial evidence for limited candidate selection."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from alma_duplicate.domain.comparison import ComparisonContext
from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.domain.queue import QueueCsvParseResult


class SpatialStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    INVALID = "INVALID"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class SkyPosition:
    ra_deg: float
    dec_deg: float
    frame: str


@dataclass(frozen=True, slots=True)
class CircleFootprint:
    center: SkyPosition
    radius_deg: float


@dataclass(frozen=True, slots=True)
class PositionInterpretation:
    """Explicit, row-scoped external interpretation, never inferred from a name."""
    context_id: str
    frame: str
    target_kind: str
    decision_ref: str

    def __post_init__(self):
        if not self.context_id.strip() or not self.decision_ref.strip():
            raise ValueError("Interpretation needs a context identity and evidence reference")


@dataclass(frozen=True, slots=True)
class SpatialEvidence:
    context: ComparisonContext
    source_record: ArchiveQueryResult | QueueCsvParseResult
    center: SkyPosition | None
    center_status: SpatialStatus
    footprint: CircleFootprint | None
    footprint_status: SpatialStatus
    geometry: str
    selection_status: SpatialStatus
    reasons: tuple[str, ...]
    interpretation: PositionInterpretation | None = None
    adapter_version: str = "1"


@dataclass(frozen=True, slots=True)
class SpatialSelection:
    context_id: str
    status: str  # INSIDE, OUTSIDE, NOT_EVALUATED
    operation: str
    separation_deg: float | None
    threshold_deg: float | None
    reasons: tuple[str, ...]
    method_version: str = "1"
    assessment: str = "NOT_EVALUATED"
