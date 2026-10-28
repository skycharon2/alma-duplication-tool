"""Step 04A: unconnected, context-local V2 aggregation of submitted LINE pairs.

Only already evaluated *complete pairs* may be combined. The caller must later
supply pairs derived from the separated LINE requirements, never physical SPWs.
This module does not authorize request execution or change legacy LINE science.
"""

from dataclasses import dataclass

from alma_duplicate.domain.line_pairing import LinePairBuildResult
from alma_duplicate.rules.aggregation import BranchAssessment, Truth, three_or
from alma_duplicate.rules.line import LINE_CRITERIA, STATUS, LinePairEvaluation

METHOD_VERSION = "archive_line_context_submitted_or_2"
SCOPE = "ONE_CANDIDATE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY"


@dataclass(frozen=True, slots=True)
class SubmittedLineContextResult:
    """V2 branch plus original reference-bound, per-requirement pair evaluations.

    This is an internal result, *not* a saved report or a search-wide verdict.
    Neither unsubmitted physical SPWs nor an inventory-completeness flag appears.
    """

    branch: BranchAssessment
    submitted_requirement_ids: tuple[str, ...]
    pairs: tuple[LinePairEvaluation, ...]
    missing_requirement_ids: tuple[str, ...]
    aggregation_version: str = "submitted_line_context_aggregation_1"


def aggregate_submitted_line_context(
    *,
    submitted_requirement_ids: tuple[str, ...],
    pairing: LinePairBuildResult,
    pairs: tuple[LinePairEvaluation, ...],
    geometry: str,
    context_supported: bool,
) -> SubmittedLineContextResult:
    """OR complete pair outcomes *within one candidate context*.

    A missing evaluation contributes UNKNOWN; an unexpected/duplicate attempt
    or mismatched pairing reference is a contract error, never ignored. The
    supplied ``context_supported`` must be computed by the future trusted V2
    context evaluator; it is not a user-controlled claim. No physical inventory
    completeness field or legacy enumeration-completeness marker is consulted.
    """
    if not isinstance(pairing, LinePairBuildResult):
        raise TypeError("Expected a LinePairBuildResult")
    if type(submitted_requirement_ids) is not tuple or type(pairs) is not tuple:
        raise TypeError("Submitted IDs and pair evaluations must be tuples")
    if type(context_supported) is not bool:
        raise TypeError("Context support must be an evaluated Boolean")
    if geometry not in {"SINGLE_POINTING", "MOSAIC"}:
        raise ValueError("Unsupported V2 geometry")
    if not pairing.candidate_context_id:
        raise ValueError("Candidate context ID is required")
    if any(type(identifier) is not str or not identifier.strip()
           for identifier in submitted_requirement_ids):
        raise ValueError("Submitted LINE requirement IDs must be nonempty strings")
    if len(set(submitted_requirement_ids)) != len(submitted_requirement_ids):
        raise ValueError("Duplicate submitted LINE requirement ID")

    submitted = set(submitted_requirement_ids)
    attempted = {}
    for attempt in pairing.attempts:
        identifier = attempt.proposed_window_id
        if identifier not in submitted:
            raise ValueError("Pairing contains an unsubmitted LINE/physical SPW window")
        if identifier in attempted:
            raise ValueError("Duplicate LINE pairing attempt")
        if attempt.candidate_context_id != pairing.candidate_context_id:
            raise ValueError("Pairing attempt belongs to another context")
        attempted[identifier] = attempt

    expected_position = "POS-MOSAIC" if geometry == "MOSAIC" else "POS-SINGLE"
    evaluated = {}
    for pair in pairs:
        if not isinstance(pair, LinePairEvaluation):
            raise TypeError("Expected a complete LinePairEvaluation")
        identifier = pair.attempt.proposed_window_id
        if identifier not in submitted or identifier not in attempted:
            raise ValueError("Pair evaluation is not for a submitted attempted LINE")
        if identifier in evaluated:
            raise ValueError("Duplicate LINE pair evaluation")
        if pair.attempt != attempted[identifier]:
            raise ValueError("Pair evaluation does not match its pairing attempt")
        if pair.attempt.candidate_context_id != pairing.candidate_context_id:
            raise ValueError("Pair evaluation belongs to another candidate context")
        if pair.criteria[0].criterion_id != expected_position:
            raise ValueError("Pair evaluation uses the wrong spatial geometry")
        if pair.method_version != "archive_line_pair_and_1":
            raise ValueError(
                "V2 context OR requires the approved six-criterion pair method"
            )
        evaluated[identifier] = pair

    ordered_pairs = tuple(
        evaluated[identifier] for identifier in submitted_requirement_ids
        if identifier in evaluated
    )
    missing = tuple(identifier for identifier in submitted_requirement_ids
                    if identifier not in evaluated)
    reasons = []
    if not submitted_requirement_ids:
        reasons.append("NO_SUBMITTED_LINE_REQUIREMENTS")
    if missing:
        reasons.append("SUBMITTED_LINE_PAIRS_INCOMPLETE")
    if any(pair.truth is Truth.UNKNOWN for pair in ordered_pairs):
        reasons.append("UNRESOLVED_SUBMITTED_LINE_PAIRS")
    if not context_supported:
        reasons.append("BRANCH_SCOPE_UNSUPPORTED")

    # The missing requirements are unknown, not assumed false.  A definitive
    # TRUE still satisfies a three-valued OR; unsupported context always wins.
    truth = (three_or((*[pair.truth for pair in ordered_pairs],
                       *(Truth.UNKNOWN for _ in missing)))
             if context_supported else Truth.UNKNOWN)
    branch = BranchAssessment(
        "LINE",
        pairing.candidate_context_id,
        STATUS[truth],
        truth,
        (expected_position,) + LINE_CRITERIA[1:],
        tuple(reasons),
        method_version=METHOD_VERSION,
        scope=SCOPE,
    )
    return SubmittedLineContextResult(
        branch, submitted_requirement_ids, ordered_pairs, missing,
    )
