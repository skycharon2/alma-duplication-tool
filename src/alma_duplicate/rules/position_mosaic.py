"""Directional proposed-pointing majority within a bound Archive beam union."""
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionOutcome as O, EvaluationStatus as E,
    MethodApplicability as A, MethodApproval, CriterionIssue, EvidenceSide,
)

DECISION = 'docs/research/mosaic/SCIENCE_GATES.md#coverage-model-decision--2026-10-23'


def evaluate_mosaic_position(proposed, *, context_id, readiness=None, selections=None,
                             hpbw_coefficient=1.13, boundary_epsilon_arcsec=0.000001,
                             assume_uniform_field_antennas=False):
    """Return the common criterion contract plus traceable coverage evidence.

    Missing Archive coverage cannot support a negative Member-level conclusion.
    A verified subset covering a strict majority suffices for a positive spatial
    result, since additional disks cannot remove covered proposed positions.
    """
    from alma_duplicate.mosaic_coverage_union import assess_union
    if not isinstance(context_id,str) or not context_id.strip():
        raise ValueError('Candidate context identity required')
    coverage, outcome, reason = None, None, 'ARCHIVE_MOSAIC_EVIDENCE_REQUIRED'
    side = EvidenceSide.CANDIDATE
    if readiness is not None and selections:
        coverage = assess_union(proposed,readiness,selections=selections,
            hpbw_coefficient=hpbw_coefficient,boundary_epsilon_arcsec=boundary_epsilon_arcsec,
            assume_uniform_field_antennas=assume_uniform_field_antennas)
        state = coverage['spatial_condition']
        if state == 'MET':
            outcome, reason = O.SATISFIED, 'STRICT_MAJORITY_WITHIN_VERIFIED_CANDIDATE_SUBSET'
        elif state == 'PROPOSED_COMPLETENESS_UNCONFIRMED':
            reason, side = 'PROPOSED_POINTING_COMPLETENESS_REQUIRED', EvidenceSide.PROPOSED
        elif state == 'BOUNDARY_UNRESOLVED':
            reason, side = 'MOSAIC_BOUNDARY_COUNT_UNRESOLVED', EvidenceSide.METHOD
        else:
            reason = 'ARCHIVE_MEMBER_COMPLETENESS_REQUIRED_FOR_NEGATIVE_RESULT'
    derived = () if coverage is None else (
        ('proposed_pointing_count',coverage['pointing_count']),
        ('inside_count',coverage['status_counts']['INSIDE']),
        ('boundary_count',coverage['status_counts']['BOUNDARY']),
        ('covered_fraction_lower',coverage['covered_fraction_lower']),
        ('covered_fraction_upper',coverage['covered_fraction_upper']))
    criterion = CriterionResult(criterion_id='POS-MOSAIC', policy_ref=f'{POLICY_DOCUMENT}, Position',
        method_version='archive_pos_mosaic_1', approval=MethodApproval.APPROVED,
        applicability=A.APPLICABLE if outcome else A.UNRESOLVED,
        evaluation=E.EVALUATED if outcome else E.INSUFFICIENT_INFORMATION,
        outcome=outcome,context_id=context_id,proposed=None,candidate=None,
        derived=derived,reasons=(reason,),decision_refs=(DECISION,),
        issues=() if outcome else (CriterionIssue(side,reason,'mosaic.position',reason),),
        details=(('scope','POSITION_ONLY_NOT_COMPLETE_DUPLICATION_VERDICT'),),
        numeric_method='SPHERICAL_FLOAT64_EXPLICIT_BOUNDARY_BAND_INTEGER_MAJORITY')
    return criterion, coverage
