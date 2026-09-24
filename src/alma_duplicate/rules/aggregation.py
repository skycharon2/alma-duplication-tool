"""Branch-local three-valued logic; never a search-wide absence conclusion."""
from dataclasses import dataclass
from enum import StrEnum
from alma_duplicate.domain.comparison import ArchiveContextEvidence, QueueContextEvidence
from alma_duplicate.rules.model import CriterionOutcome as O
from alma_duplicate.rules.confirmed import DECISION_REF


class Truth(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def three_and(values):
    values = tuple(values)
    if Truth.FALSE in values:
        return Truth.FALSE
    return Truth.TRUE if values and all(v is Truth.TRUE for v in values) else Truth.UNKNOWN


def three_or(values):
    values = tuple(values)
    if Truth.TRUE in values:
        return Truth.TRUE
    return Truth.FALSE if values and all(v is Truth.FALSE for v in values) else Truth.UNKNOWN


@dataclass(frozen=True, slots=True)
class BranchAssessment:
    branch: str
    context_id: str
    status: str
    truth: Truth
    required_criteria: tuple[str, ...]
    reasons: tuple[str, ...] = ()
    method_version: str = "branch_three_value_1"
    decision_refs: tuple[str, ...] = (DECISION_REF,)
    scope: str = "SINGLE_COHERENT_CONTEXT_ONLY"


CONTINUUM_CRITERIA = ("POS-SINGLE", "ANGULAR", "CONT-SETUP", "CONT-FREQ", "CONT-RMS")


def aggregate_continuum(context, criteria, *, supported=True, queue_method=False):
    results = {}
    for result in criteria:
        expected_context = None if result.criterion_id == "CONT-SETUP" else context.context_id
        if result.context_id != expected_context:
            raise ValueError("Cannot aggregate evidence from different contexts")
        if result.criterion_id in results:
            raise ValueError("Duplicate criterion")
        results[result.criterion_id] = result
    if queue_method:
        from alma_duplicate.rules.queue_continuum import scope_supported
        if not isinstance(context.evidence, QueueContextEvidence):
            raise TypeError("Queue aggregation requires a Queue context")
        common = tuple(results[k] for k in ("ANGULAR", "POS-SINGLE") if k in results)
        supported = supported and scope_supported(common)
        if context.evidence.association.raw_row_id != context.evidence.row.raw_row.row_id:
            raise ValueError("Queue association belongs to another source row")
    reasons = []
    values = []
    for name in CONTINUUM_CRITERIA:
        r = results.get(name)
        if r is None or not r.eligible_for_formal_aggregation:
            values.append(Truth.UNKNOWN)
            reasons.append(f"{name}_UNRESOLVED_OR_UNAPPROVED")
        else:
            values.append(Truth.TRUE if r.outcome is O.SATISFIED else Truth.FALSE)
    if not supported or not (isinstance(context.evidence, ArchiveContextEvidence) or
                             queue_method and isinstance(context.evidence, QueueContextEvidence)):
        truth = Truth.UNKNOWN
        reasons.append("BRANCH_SCOPE_UNSUPPORTED")
    elif isinstance(context.evidence, ArchiveContextEvidence) and not context.evidence.row_link.is_linked:
        truth = Truth.UNKNOWN
        reasons.append("CANDIDATE_ASSOCIATION_UNLINKED")
    elif context.alternative_context_ids:
        truth = Truth.UNKNOWN
        reasons.append("CONFLICTING_CONTEXT_ALTERNATIVES")
    else:
        truth = three_and(values)
    status = {Truth.TRUE: "CRITERIA_MET", Truth.FALSE: "CRITERIA_NOT_MET",
              Truth.UNKNOWN: "INDETERMINATE"}[truth]
    kwargs = {}
    if queue_method:
        from alma_duplicate.rules.queue_continuum import DECISION_REF as QUEUE_REF
        kwargs = dict(method_version="queue_continuum_branch_2", decision_refs=(QUEUE_REF,))
    return BranchAssessment("CONTINUUM", context.context_id, status, truth,
                            CONTINUUM_CRITERIA, tuple(reasons), **kwargs)
