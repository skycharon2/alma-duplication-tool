"""Source-row-bound Rectangle science using existing Appendix A numerics.

All conclusions are conditional on the provisional geometry/array model.
Requested RMS is compared without overlap gain or per-pointing conversion.
"""
from dataclasses import asdict, replace

from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.domain.queue import RegularSpwEvidence
from alma_duplicate.queue_rectangle_backend import assess_queue_rectangle_csv
from alma_duplicate.queue_custom_science import aggregate_custom_arrays, REQUIRED
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from alma_duplicate.reporting import json_value
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.aggregation import BranchAssessment, Truth, aggregate_continuum, criterion_truth, three_and, three_or
from alma_duplicate.rules.confirmed import approve_setup
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
from alma_duplicate.rules.queue_continuum import evaluate_queue_continuum
from alma_duplicate.rules.queue_line import evaluate_queue_line_numerical, STATUS
from alma_duplicate.rules.model import (CriterionResult, CriterionOutcome as O,
    EvaluationStatus as E, MethodApplicability as A, MethodApproval, POLICY_DOCUMENT)

DECISION = 'docs/queue_rectangle_grid.md#scientific-assessment'
MAX_SPECTRAL_PAIRS = 100_000


def _common(request, context, position):
    supported = isinstance(context.evidence.row.spectral, RegularSpwEvidence)
    details = (('common_scope', 'SUPPORTED_RECTANGLE' if supported else 'UNRESOLVED'),
               ('array_scope', 'CSV_INFERRED'), ('geometry_model_status', 'PROVISIONAL'))
    angular = replace(evaluate_angular_resolution(request, context),
        method_version='queue_rectangle_angular_1', approval=MethodApproval.APPROVED,
        details=details, decision_refs=(DECISION,))
    known = position['outcome'] != 'UNKNOWN'
    spatial = CriterionResult(criterion_id='POS-MOSAIC', policy_ref=f'{POLICY_DOCUMENT}, Position',
        method_version='queue_rectangle_position_1', approval=MethodApproval.APPROVED,
        applicability=A.APPLICABLE if known else A.UNRESOLVED,
        evaluation=E.EVALUATED if known else E.INSUFFICIENT_INFORMATION,
        outcome=O(position['outcome']) if known else None, context_id=context.context_id,
        proposed=None, candidate=None, reasons=tuple(position['reasons']), details=details,
        decision_refs=(DECISION,), derived=(('antenna_diameter_m', position['diameter_m']),),
        numeric_method='SPHERICAL_EXPLICIT_BOUNDARY_INTEGER_MAJORITY')
    return angular, spatial


def _rms_metadata(criterion, proposed):
    if criterion.criterion_id not in ('CONT-RMS', 'LINE-RMS'):
        return criterion
    return replace(criterion, details=criterion.details + (
        ('candidate_mosaic_rms_basis', 'RECTANGLE_COMBINED_IMAGE_REQUEST'),
        ('proposed_mosaic_rms_basis', str(proposed.get('sensitivity_basis', 'UNSPECIFIED'))),
        ('rms_comparison_basis', 'REQUESTED_RMS_EXISTING_APPENDIX_A_NUMERICS'),
        ('mosaic_overlap_gain', 'NONE'), ('rms_basis_conversion', 'NONE')))


def assess_queue_rectangle_science(parsed, request, proposed, *, candidate_id=None,
                                   nominal_conversion=None, prepared=None):
    """One row and one array per complete AND, then complete array-branch OR."""
    if prepared is not None:
        from alma_duplicate.rules.submitted_line_evaluation import PreparedSubmittedLineRequest
        if not isinstance(prepared, PreparedSubmittedLineRequest) or prepared.line_request is not request:
            raise ValueError('Prepared request must own these scientific operands')
    request.require_implemented_line_scope()
    if request.target_kind != 'FIXED' or request.geometry != 'MOSAIC':
        raise ValueError('Fixed Mosaic scientific request required')
    if not request.intents or any(i not in ('CONTINUUM', 'LINE') for i in request.intents):
        raise ValueError('Select CONTINUUM and/or LINE science')
    if (not isinstance(proposed, dict) or not request.target_name or
        proposed.get('source_name') != request.target_name or proposed.get('setup_id') != request.setup_id):
        raise ValueError('Proposed pointing list must bind to request target and setup')
    report = assess_queue_rectangle_csv(parsed, proposed, candidate_id=candidate_id)
    contexts = {c.reference.raw_row_id: c for c in build_queue_contexts(parsed).contexts}
    cont_request = prepared.continuum_request if prepared is not None else request if 'CONTINUUM' in request.intents else None
    setup = (approve_setup(evaluate_continuum_setup(cont_request, nominal_conversion=nominal_conversion),
             nominal_conversion=nominal_conversion) if cont_request is not None else None)
    work = sum(len(contexts[c['geometry']['source_row_id']].evidence.row.spectral.spws)*
               len(request.spectral_windows)*len(c['position']['beam_variants'])
               for c in report['candidates'] if isinstance(
                   contexts[c['geometry']['source_row_id']].evidence.row.spectral, RegularSpwEvidence))
    if work > MAX_SPECTRAL_PAIRS:
        raise ValueError('Rectangle science spectral pair budget exceeded')
    for candidate in report['candidates']:
        row_id = candidate['geometry']['source_row_id']
        context = replace(contexts[row_id], context_id=f"QUEUE-RECTANGLE:{candidate['candidate_id']}")
        variants = []
        for position in candidate['position']['beam_variants']:
            common = _common(request, context, position)
            criteria, branches, pairs = list(common), [], []
            if setup is not None:
                numerical = tuple(_rms_metadata(c, proposed) for c in
                    evaluate_queue_continuum(cont_request, context, common, mosaic=True))
                criteria.extend(numerical)
                branches.append(aggregate_continuum(context, (setup, *common, *numerical),
                                                    queue_method=True, mosaic=True))
            if 'LINE' in request.intents:
                pairing = build_queue_line_pairs(request, context, mosaic=True)
                if prepared is not None:
                    pairing = replace(pairing, proposed_enumeration_complete=True,
                        reasons=tuple(r for r in pairing.reasons if r != 'PROPOSED_ENUMERATION_INCOMPLETE'))
                for attempt in pairing.attempts:
                    numerical = tuple(_rms_metadata(c, proposed) for c in
                                      evaluate_queue_line_numerical(request, context, attempt))
                    operands = (common[1], common[0], *numerical)
                    truth = three_and(criterion_truth(c) for c in operands)
                    pairs.append(dict(reference=asdict(attempt.reference), criteria=[asdict(c) for c in operands],
                        truth=truth, status=STATUS[truth], preparation_reasons=list(attempt.reasons)))
                truths = [p['truth'] for p in pairs]
                if not pairing.proposed_enumeration_complete or not pairing.candidate_enumeration_complete:
                    truths.append(Truth.UNKNOWN)
                truth = three_or(truths)
                branches.append(BranchAssessment('LINE', context.context_id, STATUS[truth], truth,
                    REQUIRED['LINE'], tuple(pairing.reasons), method_version='queue_rectangle_line_pairs_1'))
            branches = [replace(b, method_version=f'queue_rectangle_{b.branch.lower()}_1',
                decision_refs=(DECISION,), scope='ONE_RECTANGLE_ROW_SAME_ARRAY_MODEL_CONDITIONAL') for b in branches]
            variants.append(dict(diameter_m=position['diameter_m'], criteria=criteria, branches=branches, line_pairs=pairs))
        # Existing validator enforces exact array inventory, context and required
        # criteria. Its Custom-labelled metadata is replaced for this adapter.
        combined = aggregate_custom_arrays(context.context_id,
            candidate['position']['array_inference']['diameters_m'], variants)
        if not variants:
            combined = tuple(BranchAssessment(i, context.context_id, 'INDETERMINATE', Truth.UNKNOWN,
                REQUIRED[i], ('ARRAY_INFERENCE_UNRESOLVED',)) for i in request.intents)
        combined = tuple(replace(b, method_version='queue_rectangle_array_or_1', decision_refs=(DECISION,),
            scope='ONE_RECTANGLE_ROW_COMPLETE_ARRAY_BRANCHES_MODEL_CONDITIONAL') for b in combined)
        candidate['science'] = dict(context_id=context.context_id, source_row_id=row_id,
            model_status='PROVISIONAL', scientific_candidate_completeness='NOT_ESTABLISHED',
            branches=[asdict(b) for b in combined],
            matching_arrays_by_intent={i:[v['diameter_m'] for v in variants if any(
                b.branch == i and b.truth is Truth.TRUE for b in v['branches'])] for i in request.intents},
            variants=[dict(diameter_m=v['diameter_m'], criteria=[asdict(c) for c in v['criteria']],
                           branches=[asdict(b) for b in v['branches']], line_pairs=v['line_pairs']) for v in variants])
    report.update(schema_version='queue_rectangle_csv_science_1',
        scientific_status='COMPLETE_BRANCHES_EVALUATED_UNDER_PROVISIONAL_CSV_MODEL',
        duplication_status='PER_CANDIDATE_AND_INTENT_RESULTS_NO_SEARCH_WIDE_ABSENCE_CLAIM',
        array_aggregation='COMPLETE_SAME_CANDIDATE_ARRAY_BRANCHES_OR',
        scientific_request=json_value(request.raw_input), request_criteria=[] if setup is None else [asdict(setup)])
    report['summary']['matching_candidates_by_intent'] = {i:sum(bool(c['science']['matching_arrays_by_intent'][i])
        for c in report['candidates']) for i in request.intents}
    return report
