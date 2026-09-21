"""Build traceable proposed-window/candidate-SPW attempts; no policy verdicts."""

from alma_duplicate.domain.comparison import ArchiveContextEvidence, ComparisonContext
from alma_duplicate.domain.proposed_observation import ProposedObservationRequest
from alma_duplicate.domain.line_pairing import (
    LinePairingReference,
    LinePairAttempt,
    LinePairBuildResult,
)
from alma_duplicate.proposed_line import prepare_line_window


def build_line_pairs(
    request: ProposedObservationRequest, context: ComparisonContext
) -> LinePairBuildResult:
    """Visit every listed window, including out-of-band or incomplete attempts.

    Candidate data remain reference-bound. The builder never selects a best
    sensitivity, substitutes a row scalar, filters coverage or merges contexts.
    """
    if "LINE" not in request.intents:
        return LinePairBuildResult(
            context.context_id,
            (),
            request.setup_complete is True,
            ("LINE_NOT_SELECTED",),
        )
    attempts = []
    for window in request.spectral_windows:
        planned = prepare_line_window(
            window, request.sensitivities, request.source_redshift
        )
        reasons = list(planned.reasons)
        reference = None
        mode = None
        status = "UNRESOLVED"
        evidence = context.evidence
        if request.target_kind != "FIXED" or request.geometry != "SINGLE_POINTING":
            reasons.append("FIXED_SINGLE_POINT_REQUEST_REQUIRED")
            status = "UNSUPPORTED"
        elif not isinstance(evidence, ArchiveContextEvidence):
            reasons.append("ARCHIVE_LINE_MAPPING_REQUIRED")
            status = "UNSUPPORTED"
        elif evidence.prepared.normalized_metadata.is_mosaic.value is not False:
            reasons.append("SINGLE_FIELD_CANDIDATE_REQUIRED")
            status = "UNSUPPORTED"
        else:
            mode = evidence.mode_evidence
            if mode is None:
                reasons.append("CANDIDATE_MODE_EVIDENCE_REQUIRED")
            elif (
                mode.source_record_id != context.reference.source_record_id
                or mode.association != evidence.row_link.association_key
                or context.reference.raw_row_id
                not in {o.raw_row_id for o in mode.observations}
            ):
                raise ValueError(
                    "Mode evidence belongs to another source/association/row"
                )
            elif mode.status != "AVAILABLE":
                reasons.extend(mode.reasons)
            if context.alternative_context_ids:
                reasons.append("CONFLICTING_CONTEXT_ALTERNATIVES")
            if (
                not evidence.row_link.is_linked
                or not evidence.support_mapping.is_assigned
            ):
                reasons.append("SOURCE_SPW_COMPONENT_UNASSIGNED")
            if (
                planned.sensitivity_id is not None
                and evidence.support_mapping.component_ref is not None
            ):
                ref = LinePairingReference(
                    request.setup_id,
                    window.window_id,
                    planned.sensitivity_id,
                    context.context_id,
                    context.reference.source_record_id,
                    evidence.row_link.association_key,
                    evidence.support_mapping.component_ref,
                )
                try:
                    _, _, component = ref.resolve(request, context)
                except ValueError:
                    reasons.append("PAIR_REFERENCE_UNRESOLVED")
                else:
                    reference, status = ref, "RESOLVED"
                    if component.frequency_interval is None:
                        reasons.append("EXACT_COMPONENT_INTERVAL_REQUIRED")
                    if component.resolution is None:
                        reasons.append("COMPONENT_RESOLUTION_REQUIRED")
                    if not any(s.basis == "10km/s" for s in component.sensitivities):
                        reasons.append("COMPONENT_10KMS_RMS_REQUIRED")
        if window.correlator_mode == "UNKNOWN":
            reasons.append("PROPOSED_MODE_REQUIRED")
        attempts.append(
            LinePairAttempt(
                window.window_id,
                context.context_id,
                reference,
                planned,
                mode,
                status,
                "AVAILABLE" if not reasons else "INCOMPLETE",
                tuple(dict.fromkeys(reasons)),
            )
        )
    return LinePairBuildResult(
        context.context_id,
        tuple(attempts),
        request.setup_complete is True,
        () if attempts else ("NO_PROPOSED_LINE_WINDOWS",),
    )
