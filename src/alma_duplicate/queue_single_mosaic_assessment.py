"""Single Pointing comparisons against grouped Custom and Rectangle coverage."""
from alma_duplicate.domain.queue import QueueMosaicKind, SpectralScanEvidence
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.queue_custom_backend import assess_queue_custom_csv
from alma_duplicate.queue_rectangle_backend import assess_queue_rectangle_csv
from alma_duplicate.queue_mosaic_inputs import load_snapshot, validate_inputs
from alma_duplicate.queue_mosaic_row_science import evaluate_row_candidates
from alma_duplicate.reporting import json_value


def assess_single_mosaics(validated, *, options, sources, input_sha256, report_detail, prepared=None):
    from alma_duplicate.assessment import AssessmentResult, AssessmentStatus

    request = validated.request
    if request.geometry != 'SINGLE_POINTING' or request.position is None:
        raise ValueError('Fixed Single Pointing coordinates required')
    proposed = dict(source_name=request.target_name, setup_id=request.setup_id,
        frame_basis='USER_CONFIRMED_FIXED_ICRS', completeness='USER_CONFIRMED_COMPLETE',
        sensitivity_basis='PER_POINTING', points=[dict(id='target', frame='ICRS',
            ra_deg=request.position.ra_deg, dec_deg=request.position.dec_deg)])
    validated = validate_inputs(validated, proposed, options, sources, report_detail,
                                geometry='SINGLE_POINTING')
    parsed, source = load_snapshot(sources)
    document = dict(schema_version='queue_single_mosaics_assessment_1',
        report_kind='QUEUE_SINGLE_TO_MOSAIC', input_sha256=input_sha256,
        scientific_request=json_value(request.raw_input), sources={'QUEUE': source},
        geometry_reports={}, inventory=None, search_completeness='NOT_ESTABLISHED',
        duplication_status='NO_SEARCH_WIDE_ABSENCE_CLAIM')
    status = AssessmentStatus.SOURCES_UNAVAILABLE
    if parsed is not None and parsed.can_reconstruct:
        contexts = {c.reference.raw_row_id: c for c in build_queue_contexts(parsed).contexts}
        represented = set()
        for kind, backend in (('custom', assess_queue_custom_csv), ('rectangle', assess_queue_rectangle_csv)):
            report = backend(parsed, proposed, boundary_epsilon_arcsec=0)
            for candidate in report['candidates']:
                if kind == 'custom':
                    ids = [r['source_row_id'] for r in candidate['source_rows']]
                    candidate['geometry'] = dict(source_row_id=ids[0])
                    first = contexts[ids[0]].evidence.row
                    if any(contexts[i].evidence.row.spectral != first.spectral
                           or contexts[i].evidence.row.request != first.request for i in ids):
                        raise ValueError('Custom group has conflicting scientific operands')
                else:
                    ids = [candidate['geometry']['source_row_id']]
                if represented.intersection(ids):
                    raise ValueError('Candidate source rows overlap')
                represented.update(ids)
                position = candidate['position']
                position.update(criterion_id='POS-SINGLE', threshold='POINT_WITHIN_CANDIDATE_BEAM_UNION',
                                proposed_geometry='SINGLE_POINTING')
                for variant in position['beam_variants']:
                    variant['criterion_id'] = 'POS-SINGLE'
                    coverage = variant['coverage']
                    if coverage is not None and coverage['association_confirmed']:
                        probe = variant['points'][0]
                        for relation in probe['relations']:
                            relation['relation'] = ('INSIDE' if relation['separation_arcsec'] <=
                                variant['radius_arcsec'] else 'OUTSIDE')
                        inside = any(r['relation'] == 'INSIDE' for r in probe['relations'])
                        probe['matched_point_ids'] = [r['candidate_point_id'] for r in probe['relations']
                                                      if r['relation'] == 'INSIDE']
                        probe['status'] = 'INSIDE' if inside else 'OUTSIDE' if coverage['complete'] else 'UNKNOWN'
                        variant['outcome'] = {'INSIDE': 'SATISFIED', 'OUTSIDE': 'NOT_SATISFIED',
                                              'UNKNOWN': 'UNKNOWN'}[probe['status']]
                        variant['counts'] = {key: int(key == probe['status'])
                                             for key in ('INSIDE', 'OUTSIDE', 'BOUNDARY', 'UNKNOWN')}
                        variant['covered_count_lower'] = variant['covered_fraction_lower'] = int(inside)
                        variant['covered_count_upper'] = variant['covered_fraction_upper'] = int(
                            probe['status'] != 'OUTSIDE')
                    if kind == 'custom':
                        variant['model_status'] = report['model_status'] if variant['outcome'] != 'UNKNOWN' else 'UNRESOLVED'
                        variant['geometry_model_status'] = variant['model_status']
                position['boundary_scope'] = 'INCLUSIVE_NO_EQUALITY_BAND'

            document['geometry_reports'][kind.upper()] = evaluate_row_candidates(
                report, contexts, request, proposed, kind=kind,
                decision='docs/queue_single_mosaics.md', nominal_conversion=options.nominal_conversion, prepared=prepared)
        expected = {r.raw_row.row_id.value for r in parsed.row_inputs
                    if r.spatial.mosaic_kind in (QueueMosaicKind.CUSTOM_POINTING,
                                                 QueueMosaicKind.RECTANGULAR_MOSAIC)}
        if represented != expected:
            raise ValueError('Candidate inventory omits supported Mosaic rows')
        rows = []
        for row in parsed.row_inputs:
            row_id = row.raw_row.row_id.value
            reasons = []
            if row_id not in represented:
                reasons.append('OUTSIDE_SINGLE_TO_MOSAIC_SCOPE')
            if row.request.use_tp:
                reasons.append('TP_COVERAGE_NOT_MODELLED')
            if isinstance(row.spectral, SpectralScanEvidence):
                reasons.append('SPECTRAL_SCAN_NOT_EXPANDED')
            if row.spatial.coordinate_system_raw.strip().lower() == 'galactic':
                reasons.append('GALACTIC_RECONSTRUCTION_UNSUPPORTED')
            rows.append(dict(source_row_id=row_id, geometry_kind=row.spatial.mosaic_kind.value,
                             evaluated=row_id in represented, limitations=reasons))
        document['inventory'] = dict(source_rows=rows, evaluated_source_rows=len(represented),
                                    unevaluated_source_rows=len(rows)-len(represented))
        status = AssessmentStatus.COMPLETED
    document['assessment_status'] = status.value
    return AssessmentResult(status, validated, document)
