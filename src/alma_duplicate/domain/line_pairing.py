"""Reference-bound line-pairing and preparation result contracts.

No copied frequency, mode, resolution or RMS scalars: all candidate values must
be resolved through the same ComparisonContext and selected support component.
The builder records resolved and unresolved attempts without scientific verdicts.
"""
from dataclasses import dataclass
from alma_duplicate.domain.line_evidence import ProposedLineEvidence, ArchiveModeEvidence

from alma_duplicate.domain.comparison import ArchiveContextEvidence, ComparisonContext
from alma_duplicate.domain.proposed_observation import ProposedObservationRequest
from alma_duplicate.domain.reconstruction import SourceSpwAssociationKey, SupportComponentRef


@dataclass(frozen=True, slots=True)
class LinePairingReference:
    proposed_setup_id: str
    proposed_window_id: str
    proposed_sensitivity_id: str
    candidate_context_id: str
    candidate_source_record_id: str
    candidate_association: SourceSpwAssociationKey
    candidate_component: SupportComponentRef
    model_version: str = "line_pairing_reference_1"

    def resolve(self, request: ProposedObservationRequest, context: ComparisonContext):
        """Resolve immutable references; reject cross-SPW/source/setup borrowing."""
        if not isinstance(self.candidate_component, SupportComponentRef):
            raise ValueError("Pair requires an assigned component reference")
        if request.setup_id != self.proposed_setup_id:
            raise ValueError("Pair belongs to another proposed setup")
        windows = [w for w in request.spectral_windows if w.window_id == self.proposed_window_id]
        sensitivities = [s for s in request.sensitivities if s.sensitivity_id == self.proposed_sensitivity_id]
        if (len(windows) != 1 or len(sensitivities) != 1 or sensitivities[0].purpose != "LINE"
                or sensitivities[0].scope != "WINDOW"
                or sensitivities[0].window_ids != (self.proposed_window_id,)
                or sensitivities[0].setup_id not in (None, request.setup_id)):
            raise ValueError("Pair requires one line window and its own sensitivity declaration")
        if (context.context_id != self.candidate_context_id
                or context.reference.source_record_id != self.candidate_source_record_id
                or not isinstance(context.evidence, ArchiveContextEvidence)):
            raise ValueError("Pair belongs to another candidate context/source")
        evidence = context.evidence
        if (evidence.prepared.raw_row_id != context.reference.raw_row_id
                or evidence.row_link.raw_row_id != context.reference.raw_row_id
                or self.candidate_component.raw_row_id != context.reference.raw_row_id):
            raise ValueError("Pair component belongs to another raw row")
        if context.alternative_context_ids:
            raise ValueError("Conflicting candidate alternatives cannot supply a unique pair")
        if (evidence.row_link.association_key != self.candidate_association
                or evidence.support_mapping.association_key != self.candidate_association
                or evidence.support_mapping.component_ref != self.candidate_component):
            raise ValueError("Pair does not select the assigned Source-SPW component")
        component = evidence.support_evidence.resolve(self.candidate_component)
        if component != evidence.selected_component or not component.is_valid:
            raise ValueError("Pair component is unavailable or invalid")
        return windows[0], sensitivities[0], component


@dataclass(frozen=True, slots=True)
class LinePairAttempt:
    """Association status and missing evidence, never pass/fail criteria."""
    proposed_window_id: str
    candidate_context_id: str
    reference: LinePairingReference | None
    proposed: "ProposedLineEvidence"
    candidate_mode: "ArchiveModeEvidence | None"
    association_status: str
    evidence_status: str
    reasons: tuple[str, ...]

    def __post_init__(self):
        if self.proposed.window_id != self.proposed_window_id:
            raise ValueError("Planned evidence belongs to another window")
        if (self.reference is not None) != (self.association_status == "RESOLVED"):
            raise ValueError("Resolved status requires a pairing reference")
        if self.reference is not None and (
            self.reference.candidate_context_id != self.candidate_context_id
            or self.reference.proposed_window_id != self.proposed_window_id
            or self.reference.proposed_sensitivity_id != self.proposed.sensitivity_id
        ):
            raise ValueError("Attempt reference belongs to another pair")
        if self.evidence_status == "AVAILABLE" and (self.reasons or self.reference is None):
            raise ValueError("Available preparation requires a resolved reference and no missing evidence")


@dataclass(frozen=True, slots=True)
class LinePairBuildResult:
    candidate_context_id: str
    attempts: tuple[LinePairAttempt, ...]
    proposed_enumeration_complete: bool
    reasons: tuple[str, ...] = ()
    builder_version: str = "archive_line_pair_builder_1"
    scope: str = "ONE_RETAINED_CONTEXT_ALL_LISTED_WINDOWS"
    assessment: str = "NOT_EVALUATED"

    def __post_init__(self):
        if any(a.candidate_context_id != self.candidate_context_id for a in self.attempts):
            raise ValueError("Pair attempts belong to another candidate context")
        if len({a.proposed_window_id for a in self.attempts}) != len(self.attempts):
            raise ValueError("Repeated proposed window in one pairing result")
