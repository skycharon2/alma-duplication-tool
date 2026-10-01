"""OR complete Queue beam variants, never criteria from different variants."""

from alma_duplicate.queue_row_beam import DECISION_REF
from alma_duplicate.rules.aggregation import BranchAssessment, Truth, three_or

METHOD = "queue_beam_variant_or_1"


def aggregate_beam_variants(variants):
    if tuple(v.diameter_m for v in variants) != (7.0, 12.0):
        raise ValueError("Expected exactly the 7-m and 12-m hypotheses")
    first = variants[0].evaluation
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
                method_version=METHOD,
                decision_refs=(DECISION_REF,),
                scope="SAME_QUEUE_ROW_COMPLETE_BEAM_VARIANTS_ONLY",
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
