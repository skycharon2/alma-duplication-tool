"""Bind Queue line attempts to one physical row and one regular SPW.

Preparation only: no thresholds, beam calculation, RMS scaling or verdicts.
Consumers resolve the reference again before evaluating a criterion.
"""

from dataclasses import dataclass, field

from alma_duplicate.domain.comparison import ComparisonContext, QueueContextEvidence
from alma_duplicate.domain.line_evidence import ProposedLineEvidence
from alma_duplicate.domain.proposed_observation import ProposedObservationRequest
from alma_duplicate.domain.queue import (
    QueueMosaicKind, QueueQuantity, QueueRowInput, QueueSensitivityRequest, QueueSpw,
    RegularSpwEvidence,
)
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.queue_mode_adapter import classify_spw


def _row(context: ComparisonContext) -> QueueRowInput:
    if context.reference.source != "QUEUE" or not isinstance(context.evidence, QueueContextEvidence):
        raise ValueError("QUEUE_CONTEXT_REQUIRED")
    row = context.evidence.row
    association = context.evidence.association
    identity = row.raw_row.row_id
    if (
        context.reference.raw_row_id != identity.value
        or context.reference.source_record_id != identity.snapshot_sha256
        or association.raw_row_id != identity
        or association.group_key != row.group_key
        or association.content_fingerprint != row.raw_row.content_fingerprint
    ):
        raise ValueError("QUEUE_ROW_ASSOCIATION_MISMATCH")
    if context.alternative_context_ids:
        raise ValueError("CONFLICTING_CONTEXT_ALTERNATIVES")
    return row


@dataclass(frozen=True, slots=True)
class QueueLineCandidateEvidence:
    """Source quantities remain typed, raw-token preserving and unscaled."""

    spw: QueueSpw
    sensitivity_reference: QueueSensitivityRequest
    angular_resolution: QueueQuantity
    mode: dict
    sensitivity_binding: str = "SAME_ROW_REFERENCE_TRIPLET_NOT_SPW_RMS"


@dataclass(frozen=True, slots=True)
class QueueLinePairReference:
    proposed_setup_id: str
    proposed_window_id: str
    candidate_context_id: str
    snapshot_sha256: str
    source_row_id: str
    content_fingerprint: str
    spw_number: int
    model_version: str = "queue_line_pair_reference_1"

    def resolve(self, request: ProposedObservationRequest, context: ComparisonContext):
        """Reject foreign contexts/rows/snapshots and ambiguous SPW slots.

        Mode is derived from the selected slot in its owning row. Reference
        sensitivity is returned as a row-level triplet, never as achieved RMS.
        A missing proposal RMS does not prevent independent pair preparation.
        """
        row = _row(context)
        if request.setup_id != self.proposed_setup_id:
            raise ValueError("PAIR_PROPOSED_SETUP_MISMATCH")
        windows = [w for w in request.spectral_windows if w.window_id == self.proposed_window_id]
        if len(windows) != 1:
            raise ValueError("PAIR_PROPOSED_WINDOW_NOT_UNIQUE")
        if (
            context.context_id != self.candidate_context_id
            or row.raw_row.row_id.snapshot_sha256 != self.snapshot_sha256
            or row.raw_row.row_id.value != self.source_row_id
            or row.raw_row.content_fingerprint != self.content_fingerprint
        ):
            raise ValueError("PAIR_CANDIDATE_IDENTITY_MISMATCH")
        if not isinstance(row.spectral, RegularSpwEvidence):
            raise ValueError("SPECTRAL_SCAN_NOT_EXPANDED")
        spws = [s for s in row.spectral.spws if s.number == self.spw_number]
        if len(spws) != 1:
            raise ValueError("SPW_SLOT_NOT_UNIQUELY_BOUND_TO_ROW")
        sensitivities = tuple(
            s for s in request.sensitivities if s.setup_id in (None, request.setup_id)
        )
        proposed = prepare_line_window(windows[0], sensitivities, request.source_redshift)
        return proposed, QueueLineCandidateEvidence(
            spws[0], row.spectral.sensitivity,
            row.request.requested_angular_resolution_arcsec,
            classify_spw(row, self.spw_number),
        )


@dataclass(frozen=True, slots=True)
class QueueLinePairAttempt:
    reference: QueueLinePairReference
    proposed: ProposedLineEvidence
    candidate: QueueLineCandidateEvidence
    reasons: tuple[str, ...]
    association_status: str = "RESOLVED"
    evidence_status: str = field(init=False)

    def __post_init__(self):
        source = self.candidate.mode["source"]
        if (
            self.reference.proposed_window_id != self.proposed.window_id
            or self.reference.spw_number != self.candidate.spw.number
            or source["spw_number"] != self.reference.spw_number
            or source["source_row_id"] != self.reference.source_row_id
            or source["snapshot_sha256"] != self.reference.snapshot_sha256
        ):
            raise ValueError("PAIR_EVIDENCE_IDENTITY_MISMATCH")
        object.__setattr__(self, "evidence_status", "INCOMPLETE" if self.reasons else "AVAILABLE")


@dataclass(frozen=True, slots=True)
class QueueLinePairBuildResult:
    candidate_context_id: str
    attempts: tuple[QueueLinePairAttempt, ...]
    proposed_enumeration_complete: bool
    candidate_enumeration_complete: bool
    reasons: tuple[str, ...] = ()
    builder_version: str = "queue_line_pair_builder_1"
    scope: str = "ONE_PHYSICAL_ROW_ALL_LISTED_WINDOWS_X_REGULAR_SPWS"
    assessment: str = "NOT_EVALUATED"

    def __post_init__(self):
        keys = [(a.reference.proposed_window_id, a.reference.spw_number) for a in self.attempts]
        if len(set(keys)) != len(keys):
            raise ValueError("DUPLICATE_PAIR_ATTEMPT")
        if any(a.reference.candidate_context_id != self.candidate_context_id for a in self.attempts):
            raise ValueError("PAIR_CONTEXT_MISMATCH")


def build_queue_line_pairs(
    request: ProposedObservationRequest, context: ComparisonContext
) -> QueueLinePairBuildResult:
    """Enumerate every proposed window x occupied SPW; never filter by coverage.

    Input must come from request validation and successful strict Queue context
    construction. Completeness is only within this supplied physical row.
    Unsupported geometry is retained as a reason; it is never a negative result.
    """
    row = _row(context)
    complete = request.setup_complete is True
    if "LINE" not in request.intents:
        return QueueLinePairBuildResult(context.context_id, (), complete, False, ("LINE_NOT_SELECTED",))
    if not isinstance(row.spectral, RegularSpwEvidence):
        return QueueLinePairBuildResult(
            context.context_id, (), complete, False, ("SPECTRAL_SCAN_NOT_EXPANDED",)
        )
    numbers = [s.number for s in row.spectral.spws]
    windows = [w.window_id for w in request.spectral_windows]
    if len(set(numbers)) != len(numbers):
        raise ValueError("SPW_SLOT_NOT_UNIQUELY_BOUND_TO_ROW")
    if len(set(windows)) != len(windows):
        raise ValueError("PAIR_PROPOSED_WINDOW_NOT_UNIQUE")
    reasons = []
    if not windows:
        reasons.append("NO_PROPOSED_LINE_WINDOWS")
    if not numbers:
        reasons.append("NO_REGULAR_SPWS")
    if not complete:
        reasons.append("PROPOSED_ENUMERATION_INCOMPLETE")
    scope_reasons = []
    if request.target_kind != "FIXED" or request.geometry != "SINGLE_POINTING":
        scope_reasons.append("FIXED_SINGLE_POINT_REQUEST_REQUIRED")
    if row.spatial.mosaic_kind is not QueueMosaicKind.SINGLE_FIELD:
        scope_reasons.append("QUEUE_SINGLE_FIELD_REQUIRED")
    reasons.extend(scope_reasons)
    attempts = []
    for window in request.spectral_windows:
        for number in numbers:
            reference = QueueLinePairReference(
                request.setup_id, window.window_id, context.context_id,
                row.raw_row.row_id.snapshot_sha256, row.raw_row.row_id.value,
                row.raw_row.content_fingerprint, number,
            )
            proposed, candidate = reference.resolve(request, context)
            missing = [*scope_reasons, *proposed.reasons]
            if window.correlator_mode == "UNKNOWN":
                missing.append("PROPOSED_MODE_REQUIRED")
            if candidate.mode["mode_evidence"]["mode"] == "UNKNOWN":
                missing.extend(("QUEUE_MODE_UNRESOLVED", candidate.mode["mode_evidence"]["reason"]))
            if candidate.spw.usable_bandwidth_ghz is None:
                missing.append("QUEUE_USABLE_INTERVAL_REQUIRED")
            attempts.append(QueueLinePairAttempt(reference, proposed, candidate, tuple(dict.fromkeys(missing))))
    return QueueLinePairBuildResult(
        context.context_id, tuple(attempts), complete, bool(numbers), tuple(reasons)
    )
