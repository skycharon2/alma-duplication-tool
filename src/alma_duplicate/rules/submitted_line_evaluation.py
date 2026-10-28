"""Step 04B: internal, reference-bound V2 Archive LINE context evaluation.

Only submitted LINE requirements enter the temporary, LINE-only typed science
view. Physical SPW evidence is never converted to a requested LINE window.
Shared retrieval, report, browser and CLI entrypoints remain fail-closed until
separately reviewed Step 04C integration.
"""

from dataclasses import dataclass, replace

from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.line_pairing import LinePairBuildResult
from alma_duplicate.line_pairing import build_line_pairs
from alma_duplicate.request_validation import _Validator, validate_proposed_observation
from alma_duplicate.rules.aggregation import Truth, criterion_truth, three_and
from alma_duplicate.rules.confirmed import archive_scope
from alma_duplicate.rules.line import LinePairEvaluation, STATUS, _numerical
from alma_duplicate.rules.submitted_line import (
    SubmittedLineContextResult, aggregate_submitted_line_context,
)
from alma_duplicate.separated_setup_input import (
    SEPARATED_INPUT_CONTRACT, SeparatedSetupOperands, parse_separated_setup,
)

_SHARED_FIELDS = frozenset({
    "target_kind", "geometry", "target_name", "position", "setup_id",
    "intents", "angular_resolution", "representative_frequency",
    "representative_window_id", "array_context", "source_redshift",
})


@dataclass(frozen=True, slots=True)
class PreparedSubmittedLineRequest:
    """Internal typed LINE-only view, never a reportable legacy wire request."""

    line_request: object
    separated: SeparatedSetupOperands
    input_contract: str = SEPARATED_INPUT_CONTRACT

    @property
    def submitted_ids(self) -> tuple[str, ...]:
        return tuple(w.window_id for w in self.separated.line_windows)


@dataclass(frozen=True, slots=True)
class SubmittedLineEvaluation:
    """One candidate context; not a search-wide or published assessment."""

    pairing: LinePairBuildResult
    result: SubmittedLineContextResult
    input_contract: str = SEPARATED_INPUT_CONTRACT


def prepare_submitted_line_request(raw_request) -> PreparedSubmittedLineRequest:
    """Parse a separated request; never interpret its physical inventory as LINE.

    The shared public validator is *intentionally* still fail-closed. We require
    its sole ERROR to be SEPARATED_INPUT_NOT_EXECUTABLE before constructing an
    internal view. This is not a bypass for malformed or mixed wire contracts.
    """
    validation = validate_proposed_observation(raw_request)
    codes = [issue.code for issue in validation.errors]
    if codes != ["SEPARATED_INPUT_NOT_EXECUTABLE"]:
        raise ValueError("Invalid or unsupported separated LINE input: " + ", ".join(codes))

    validator = _Validator()
    detached = validator.snapshot(raw_request, "request")
    separated = parse_separated_setup(validator, detached)
    if separated is None or any(issue.category == "ERROR" for issue in validator.issues):
        raise ValueError("Separated LINE operand preparation failed")
    if (detached.get("line_input_contract") != SEPARATED_INPUT_CONTRACT
            or tuple(detached.get("intents", ())) != ("LINE",)
            or detached.get("target_kind") != "FIXED"
            or detached.get("geometry") not in {"SINGLE_POINTING", "MOSAIC"}):
        raise ValueError("V2 context evaluator supports FIXED Archive LINE-only inputs")
    if not separated.line_windows:
        raise ValueError("At least one submitted LINE requirement is required")

    # Reuse the already-approved shared parsers for target and angular fields.
    # Crucially this internal view contains ONLY submitted LINE operands: no
    # physical SPWs, no completeness declaration, no V2 wire marker, and no
    # client-supplied 'context_supported' authority flag.
    shared = {key: value for key, value in detached.items() if key in _SHARED_FIELDS}
    baseline = validate_proposed_observation(shared)
    if not baseline.is_valid or baseline.request is None:
        raise ValueError("Invalid shared target or angular fields")
    base_request = baseline.request
    if base_request.angular_resolution is None:
        raise ValueError("Planned angular resolution is required for V2 LINE")
    if base_request.geometry == "SINGLE_POINTING" and base_request.position is None:
        raise ValueError("Single Pointing requires an ICRS position")
    if base_request.geometry == "MOSAIC" and not base_request.target_name:
        raise ValueError("Mosaic requires an explicit target name")

    line_request = replace(
        base_request,
        spectral_windows=separated.line_windows,
        sensitivities=separated.line_sensitivities,
        setup_complete=None,
    )
    return PreparedSubmittedLineRequest(line_request, separated)


def evaluate_submitted_line_context_v2(
    prepared: PreparedSubmittedLineRequest,
    context,
    common_criteria,
) -> SubmittedLineEvaluation:
    """Evaluate six criteria per submitted LINE pair and aggregate within context.

    ``common_criteria`` must be the already-computed POS-SINGLE/POS-MOSAIC and
    ANGULAR results for this precise context. Scientific context support is
    derived here, never accepted from the browser or request JSON.
    """
    if not isinstance(prepared, PreparedSubmittedLineRequest):
        raise TypeError("Expected a validated PreparedSubmittedLineRequest")
    request = prepared.line_request
    geometry = request.geometry
    mosaic = geometry == "MOSAIC"
    position_id = "POS-MOSAIC" if mosaic else "POS-SINGLE"
    common = tuple(common_criteria)
    by_id = {criterion.criterion_id: criterion for criterion in common}
    if len(common) != 2 or len(by_id) != 2 or set(by_id) != {position_id, "ANGULAR"}:
        raise ValueError("V2 requires exactly the computed position and angular criteria")
    if any(criterion.context_id != context.context_id for criterion in common):
        raise ValueError("V2 common criteria belong to another candidate context")

    archive = (context.reference.source == "ARCHIVE"
               and isinstance(context.evidence, ArchiveContextEvidence))
    if not archive:
        raise ValueError("V2 context evaluation requires Archive evidence")
    evidence = context.evidence
    unsupported_position = {
        "UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED",
        "ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED",
        "CONFLICTING_POSITION_INTERPRETATION",
    }
    supported = (
        (archive_scope(request, context) or (mosaic and request.target_kind == "FIXED"))
        and (mosaic or evidence.prepared.normalized_metadata.is_mosaic.value is False)
        and evidence.row_link.is_linked
        and not context.alternative_context_ids
        and not unsupported_position.intersection(by_id[position_id].reasons)
    )
    # Preserve the unchanged reference-bound attempts but label their *actual*
    # selection scope; the legacy result's physical-enumeration Boolean is not
    # a V2 condition and is ignored by the new context aggregator.
    pairing = replace(
        build_line_pairs(request, context, mosaic=mosaic),
        builder_version="archive_line_pair_builder_submitted_2",
        scope="ONE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY",
    )
    pairs = []
    for attempt in pairing.attempts:
        criteria = (
            by_id[position_id],
            by_id["ANGULAR"],
            *_numerical(request, context, attempt),
        )
        truth = three_and(criterion_truth(item) for item in criteria) if supported else Truth.UNKNOWN
        reasons = tuple(
            f"{item.criterion_id}_UNRESOLVED_OR_UNAPPROVED"
            for item in criteria if not item.eligible_for_formal_aggregation
        )
        if not supported:
            reasons += ("BRANCH_SCOPE_UNSUPPORTED",)
        pairs.append(LinePairEvaluation(attempt, criteria, truth, STATUS[truth], reasons))

    result = aggregate_submitted_line_context(
        submitted_requirement_ids=prepared.submitted_ids,
        pairing=pairing,
        pairs=tuple(pairs),
        geometry=geometry,
        context_supported=supported,
    )
    return SubmittedLineEvaluation(pairing, result)
