"""OR complete source-bound beam variants, never criteria across variants.

Queue retains its method identity; Archive uses a distinct project decision.
"""

from alma_duplicate.queue_row_beam import DECISION_REF
from alma_duplicate.rules.aggregation import BranchAssessment, Truth, three_or

METHOD = "queue_beam_variant_or_1"


def aggregate_beam_variants(variants, *, source="QUEUE"):
    if tuple(v.diameter_m for v in variants) != (7.0, 12.0):
        raise ValueError("Expected exactly the 7-m and 12-m hypotheses")
    first = variants[0].evaluation
    if source not in {"ARCHIVE", "QUEUE"} or first.candidate.context.reference.source != source:
        raise ValueError("Beam aggregation source disagrees with candidate")
    if source == "ARCHIVE":
        from alma_duplicate.archive_array_evidence import DECISION_REF as decision
        method, scope = "archive_beam_variant_or_1", "SAME_ARCHIVE_SOURCE_CONTEXT_COMPLETE_BEAM_VARIANTS_ONLY"
    else:
        decision, method, scope = DECISION_REF, METHOD, "SAME_QUEUE_ROW_COMPLETE_BEAM_VARIANTS_ONLY"
    names = tuple(b.branch for b in first.branches)
    if len(set(names)) != len(names) or any(
        v.evaluation.candidate != first.candidate
        or tuple((b.branch, b.required_criteria) for b in v.evaluation.branches)
        != tuple((b.branch, b.required_criteria) for b in first.branches)
        for v in variants
    ):
        raise ValueError("Beam variants must have identical source and branch scope")
    results = []
    for index, branch in enumerate(first.branches):
        truth = three_or(v.evaluation.branches[index].truth for v in variants)
        results.append(
            BranchAssessment(
                branch.branch,
                branch.context_id,
                {
                    Truth.TRUE: "CRITERIA_MET",
                    Truth.FALSE: "CRITERIA_NOT_MET",
                    Truth.UNKNOWN: "INDETERMINATE",
                }[truth],
                truth,
                branch.required_criteria,
                ("COMPLETE_BEAM_VARIANTS_OR",),
                method_version=method,
                decision_refs=(decision,),
                scope=scope,
            )
        )
    return tuple(results)


def matching_diameters(variants, branch=None):
    return tuple(
        v.diameter_m
        for v in variants
        if any(
            b.truth is Truth.TRUE and (branch is None or b.branch == branch)
            for b in v.evaluation.branches
        )
    )
