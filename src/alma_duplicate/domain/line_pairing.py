"""Reference-only line-pairing contract for the next rule increment.

No copied frequency, mode, resolution or RMS scalars: all candidate values must
be resolved through the same ComparisonContext and selected support component.
This schema is not yet a line matcher and produces no scientific verdict.
"""
from dataclasses import dataclass

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
                or sensitivities[0].window_ids != (self.proposed_window_id,)):
            raise ValueError("Pair requires one line window and its own sensitivity declaration")
        if (context.context_id != self.candidate_context_id
                or context.reference.source_record_id != self.candidate_source_record_id
                or not isinstance(context.evidence, ArchiveContextEvidence)):
            raise ValueError("Pair belongs to another candidate context/source")
        evidence = context.evidence
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
