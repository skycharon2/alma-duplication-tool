"""Evaluate science on a candidate bound to a representative Queue row."""
from dataclasses import asdict, replace

from alma_duplicate.domain.queue import RegularSpwEvidence
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

MAX_SPECTRAL_PAIRS = 100_000


def _common(request, context, position, kind, decision):
    single = request.geometry == 'SINGLE_POINTING'
    method_kind = f'single_to_{kind}' if single else kind
    supported = isinstance(context.evidence.row.spectral, RegularSpwEvidence)
    details = (('common_scope', f'SUPPORTED_{method_kind.upper()}' if supported else 'UNRESOLVED'),
               ('array_scope', 'CSV_INFERRED'),
               ('geometry_model_status', position.get('geometry_model_status', 'PROVISIONAL')))
    angular = replace(evaluate_angular_resolution(request, context),
        method_version=f'queue_{method_kind}_angular_1', approval=MethodApproval.APPROVED,
        details=details, decision_refs=(decision,))
    known = position['outcome'] != 'UNKNOWN'
    spatial = CriterionResult(criterion_id='POS-SINGLE' if single else 'POS-MOSAIC', policy_ref=f'{POLICY_DOCUMENT}, Position',
        method_version=f'queue_{method_kind}_position_1', approval=MethodApproval.APPROVED,
        applicability=A.APPLICABLE if known else A.UNRESOLVED,
        evaluation=E.EVALUATED if known else E.INSUFFICIENT_INFORMATION,
        outcome=O(position['outcome']) if known else None, context_id=context.context_id,
        proposed=None, candidate=None, reasons=tuple(position['reasons']), details=details,
        decision_refs=(decision,), derived=(('antenna_diameter_m', position['diameter_m']),),
        numeric_method='SPHERICAL_BEAM_UNION_SINGLE_POINT' if single else 'SPHERICAL_EXPLICIT_BOUNDARY_INTEGER_MAJORITY')
    return angular, spatial


def _rms_metadata(criterion, proposed, kind):
    if criterion.criterion_id not in ('CONT-RMS', 'LINE-RMS'):
        return criterion
    return replace(criterion, details=criterion.details + (
        ('candidate_mosaic_rms_basis', {'rectangle': 'RECTANGLE_COMBINED_IMAGE_REQUEST', 'custom': 'CUSTOM_PER_POINTING_REQUEST', 'single_field': 'SINGLE_FIELD_REQUEST'}[kind]),
        ('proposed_mosaic_rms_basis', str(proposed.get('sensitivity_basis', 'UNSPECIFIED'))),
        ('rms_comparison_basis', 'REQUESTED_RMS_EXISTING_APPENDIX_A_NUMERICS'),
        ('mosaic_overlap_gain', 'NONE'), ('rms_basis_conversion', 'NONE')))


def evaluate_row_candidates(report, contexts, request, proposed, *, kind, decision, nominal_conversion, prepared=None):
    single = request.geometry == 'SINGLE_POINTING'
    method_kind = f'single_to_{kind}' if single else kind
    required = {intent: ('POS-SINGLE', *criteria[1:]) for intent, criteria in REQUIRED.items()} if single else REQUIRED
    cont_request = prepared.continuum_request if prepared is not None else request if 'CONTINUUM' in request.intents else None
    setup = (approve_setup(evaluate_continuum_setup(cont_request, nominal_conversion=nominal_conversion),
             nominal_conversion=nominal_conversion) if cont_request is not None else None)
    work = sum(len(contexts[c['geometry']['source_row_id']].evidence.row.spectral.spws)*
               len(request.spectral_windows)*len(c['position']['beam_variants'])
               for c in report['candidates'] if isinstance(
                   contexts[c['geometry']['source_row_id']].evidence.row.spectral, RegularSpwEvidence))
    if work > MAX_SPECTRAL_PAIRS:
        raise ValueError(f'{kind.title()} science spectral pair budget exceeded')
    for candidate in report['candidates']:
        row_id = candidate['geometry']['source_row_id']
        context = replace(contexts[row_id], context_id=f"QUEUE-{kind.upper()}:{candidate['candidate_id']}")
        variants = []
        for position in candidate['position']['beam_variants']:
            common = _common(request, context, position, kind, decision)
            criteria, branches, pairs = list(common), [], []
            if setup is not None:
                numerical = tuple(_rms_metadata(c, proposed, kind) for c in
                    evaluate_queue_continuum(cont_request, context, common, mosaic=not single, candidate_mosaic=single))
                criteria.extend(numerical)
                branches.append(aggregate_continuum(context, (setup, *common, *numerical),
                                                    queue_method=True, mosaic=not single))
            if 'LINE' in request.intents:
                pairing = build_queue_line_pairs(request, context, mosaic=not single, candidate_mosaic=single)
                if prepared is not None:
                    pairing = replace(pairing, proposed_enumeration_complete=True,
                        reasons=tuple(r for r in pairing.reasons if r != 'PROPOSED_ENUMERATION_INCOMPLETE'))
                for attempt in pairing.attempts:
                    numerical = tuple(_rms_metadata(c, proposed, kind) for c in
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
                    required['LINE'], tuple(pairing.reasons), method_version=f'queue_{method_kind}_line_pairs_1'))
            branches = [replace(b, method_version=f'queue_{method_kind}_{b.branch.lower()}_1',
                decision_refs=(decision,), scope=f'ONE_{kind.upper()}_ROW_SAME_ARRAY_MODEL_CONDITIONAL') for b in branches]
            variants.append(dict(diameter_m=position['diameter_m'], criteria=criteria, branches=branches, line_pairs=pairs))
        # Existing validator enforces exact array inventory, context and required
        # criteria. Its Custom-labelled metadata is replaced for this adapter.
        combined = aggregate_custom_arrays(context.context_id,
            candidate['position']['array_inference']['diameters_m'], variants, required=required)
        if not variants:
            combined = tuple(BranchAssessment(i, context.context_id, 'INDETERMINATE', Truth.UNKNOWN,
                required[i], ('ARRAY_INFERENCE_UNRESOLVED',)) for i in request.intents)
        combined = tuple(replace(b, method_version=f'queue_{method_kind}_array_or_1', decision_refs=(decision,),
            scope=f'ONE_{kind.upper()}_ROW_COMPLETE_ARRAY_BRANCHES_MODEL_CONDITIONAL') for b in combined)
        known_model = kind in ('custom', 'rectangle')
        accepted = (known_model and bool(variants)
            and all(p.get('geometry_model_status') == 'PROJECT_ACCEPTED'
                    and p.get('outcome') != 'UNKNOWN'
                    for p in candidate['position']['beam_variants']))
        model_status = ('PROJECT_ACCEPTED' if accepted else
                        'UNRESOLVED' if known_model else 'PROVISIONAL')
        # Only Rectangle has an established per-intent completeness policy.
        rectangle_complete = kind == 'rectangle' and accepted
        intent_completeness = {b.branch: (
            'COMPLETE_FOR_EVALUATED_INTENT' if rectangle_complete and b.truth is Truth.TRUE
            else 'NOT_ESTABLISHED') for b in combined}
        candidate_completeness = (
            'COMPLETE_FOR_EVALUATED_INTENT' if rectangle_complete and combined
            and all(b.truth is Truth.TRUE for b in combined) else 'NOT_ESTABLISHED')
        candidate['science'] = dict(context_id=context.context_id, source_row_id=row_id,
            model_status=model_status, model_version=(candidate['position'].get('model_version')
                if kind == 'rectangle' else None),
            scientific_candidate_completeness=candidate_completeness,
            intent_completeness=intent_completeness,
            branches=[asdict(b) for b in combined],
            matching_arrays_by_intent={i:[v['diameter_m'] for v in variants if any(
                b.branch == i and b.truth is Truth.TRUE for b in v['branches'])] for i in request.intents},
            variants=[dict(diameter_m=v['diameter_m'], criteria=[asdict(c) for c in v['criteria']],
                           branches=[asdict(b) for b in v['branches']], line_pairs=v['line_pairs']) for v in variants])
    report.update(schema_version=f'queue_{method_kind}_csv_science_1',
        scientific_status=(f'BRANCHES_EVALUATED_WITH_PER_CANDIDATE_{kind.upper()}_MODEL_STATUS'
            if kind in ('rectangle', 'custom') else 'COMPLETE_BRANCHES_EVALUATED_UNDER_PROVISIONAL_CSV_MODEL'),
        duplication_status='PER_CANDIDATE_AND_INTENT_RESULTS_NO_SEARCH_WIDE_ABSENCE_CLAIM',
        array_aggregation='COMPLETE_SAME_CANDIDATE_ARRAY_BRANCHES_OR',
        scientific_request=json_value(request.raw_input), request_criteria=[] if setup is None else [asdict(setup)])
    report['summary']['matching_candidates_by_intent'] = {i:sum(bool(c['science']['matching_arrays_by_intent'][i])
        for c in report['candidates']) for i in request.intents}
    return report
