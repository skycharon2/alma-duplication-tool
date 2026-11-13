"""Single proposed point in supervisor-adopted Archive Mosaic coverage."""
from alma_duplicate.mosaic_region_position import assess_region_position
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionOutcome as O,
    EvaluationStatus as E, MethodApplicability as A, MethodApproval,
    CriterionIssue, EvidenceSide,
)

METHOD = 'archive_pos_single_mosaic_s_region_1'
DECISION = 'docs/development/single-point-mosaic/step03_position.md'


def evaluate_single_mosaic_region(request, context, spatial_evidence):
    old = spatial_evidence.interpretation
    reasons = []
    if old is not None and (old.frame != 'ICRS' or old.target_kind != 'FIXED'):
        reasons.append('CONFLICTING_POSITION_INTERPRETATION')
    raw = context.evidence.prepared.raw_row
    coverage = assess_region_position(
        {'points': [{'id': 'target', 'ra_deg': request.position.ra_deg,
                     'dec_deg': request.position.dec_deg}],
         'frame_basis': 'USER_CONFIRMED_FIXED_ICRS',
         'completeness': 'USER_CONFIRMED_COMPLETE'},
        raw.get('s_region'), candidate_id=context.context_id,
    )
    # Only reuse the spherical classifier, never its Mosaic majority outcome.
    status = coverage['points'][0]['status']
    if status == 'UNKNOWN':
        reasons.extend(coverage['reasons'] or ['ARCHIVE_REGION_UNAVAILABLE'])
    outcome = None if reasons else O.NOT_SATISFIED if status == 'OUTSIDE' else O.SATISFIED
    return CriterionResult(
        criterion_id='POS-SINGLE', policy_ref=f'{POLICY_DOCUMENT}, Position',
        method_version=METHOD, approval=MethodApproval.APPROVED,
        applicability=A.UNRESOLVED if reasons else A.APPLICABLE,
        evaluation=E.INSUFFICIENT_INFORMATION if reasons else E.EVALUATED,
        outcome=outcome, context_id=context.context_id, proposed=None, candidate=None,
        derived=(('point_status', status), ('boundary_arcsec', coverage['boundary_arcsec'])),
        details=(('coverage_source', 'ARCHIVE_S_REGION'),
                 ('raw_s_region', coverage['raw_s_region']),
                 ('s_region_sha256', coverage['s_region_sha256']),
                 ('polygon_convention', coverage['polygon_convention'])),
        issues=tuple(CriterionIssue(EvidenceSide.CANDIDATE, r, 'position.s_region', r) for r in reasons),
        reasons=tuple(reasons) or (('OUTSIDE_ARCHIVE_S_REGION',) if status == 'OUTSIDE'
                                  else ('WITHIN_INCLUSIVE_ARCHIVE_S_REGION',)),
        decision_refs=(DECISION,), numeric_method='SPHERICAL_REGION_INCLUSIVE_BOUNDARY_BAND',
    )
