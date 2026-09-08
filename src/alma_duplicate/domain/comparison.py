"""Traceable context construction, not candidate matching or policy verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alma_duplicate.clients.archive_adapter import PreparedArchiveRow
    from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.domain.queue import QueueCsvParseResult, QueueRowAssociation, QueueRowInput
from alma_duplicate.domain.reconstruction import (
    RowFrequencySupportEvidence, RowReconstruction, SupportMapping,
)
from alma_duplicate.domain.spectral import FrequencySupportComponent


class SourceStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"
    NOT_PROVIDED = "NOT_PROVIDED"


class EvidenceState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    source: str
    raw_row_id: str
    source_record_id: str  # Archive query run or Queue checksum, not an acquisition ID.
    parser_version: str
    reconstruction_version: str
    adapter_version: str
    component_index: int | None = None
    # Direct CSV inputs do not have persistent acquisition/run identities.
    acquisition_id: str | None = None
    parse_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Path into retained source evidence; states never imply criterion success."""

    path: str
    numeric: EvidenceState
    unit: EvidenceState
    association: EvidenceState
    reference: EvidenceState = EvidenceState.UNKNOWN
    method: EvidenceState = EvidenceState.NOT_IMPLEMENTED
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArchiveContextEvidence:
    prepared: PreparedArchiveRow
    row_link: RowReconstruction
    support_mapping: SupportMapping
    support_evidence: RowFrequencySupportEvidence
    selected_component: FrequencySupportComponent | None


@dataclass(frozen=True, slots=True)
class QueueContextEvidence:
    row: QueueRowInput
    association: QueueRowAssociation


@dataclass(frozen=True, slots=True)
class ComparisonContext:
    context_id: str
    reference: EvidenceReference
    evidence: ArchiveContextEvidence | QueueContextEvidence
    items: tuple[EvidenceItem, ...]
    # IDs with the same Archive association; retained, never collapsed.
    alternative_context_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    model_version: str = "1"


@dataclass(frozen=True, slots=True)
class ComparisonSourceResult:
    source: str
    status: SourceStatus
    source_record: ArchiveQueryResult | QueueCsvParseResult | None
    contexts: tuple[ComparisonContext, ...] = ()
    reasons: tuple[str, ...] = ()
    # Completeness refers only to the supplied query/file, not all sky/Queue coverage.
    scope: str = "SUPPLIED_SOURCE_ONLY"


@dataclass(frozen=True, slots=True)
class ComparisonPreparation:
    validation: RequestValidationResult
    archive: ComparisonSourceResult
    queue: ComparisonSourceResult
    construction_version: str = "1"
    # No predicates or criteria execute in this module.
    search_execution: str = "NOT_EXECUTED"
    assessment: str = "NOT_EVALUATED"
