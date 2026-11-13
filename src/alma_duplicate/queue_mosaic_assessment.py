"""Assess both Queue Mosaic geometries against one parsed snapshot."""
from collections import Counter

from alma_duplicate.domain.queue import QueueMosaicKind, SpectralScanEvidence
from alma_duplicate.queue_custom_science import assess_queue_custom_science
from alma_duplicate.queue_mosaic_inputs import load_snapshot, validate_inputs
from alma_duplicate.queue_rectangle_science import assess_queue_rectangle_science
from alma_duplicate.queue_single_field_mosaic import assess_single_field_science
from alma_duplicate.reporting import json_value


def assess_queue_mosaic(validated, proposed, *, options, sources, input_sha256, report_detail, prepared=None):
    from alma_duplicate.assessment import AssessmentResult, AssessmentStatus

    validated = validate_inputs(validated, proposed, options, sources, report_detail)
    request = validated.request
    parsed, source = load_snapshot(sources)
    report = dict(schema_version='queue_mosaic_assessment_1', report_kind='QUEUE_MOSAIC',
                  proposed=proposed, scientific_request=json_value(request.raw_input),
                  input_sha256=input_sha256, source_mode='QUEUE_CSV', sources={'QUEUE': source},
                  evaluation_configuration=dict(science_intents=list(request.intents),
                      nominal_conversion=options.nominal_conversion, report_detail=report_detail),
                  search_completeness='NOT_ESTABLISHED', inventory=None,
                  geometry_reports={}, duplication_status='NO_SEARCH_WIDE_ABSENCE_CLAIM')
    status = AssessmentStatus.SOURCES_UNAVAILABLE
    if parsed is not None and parsed.can_reconstruct:
        reports = report['geometry_reports']
        counts = {}
        represented = Counter()
        for kind, evaluate in ((QueueMosaicKind.CUSTOM_POINTING, assess_queue_custom_science),
                               (QueueMosaicKind.RECTANGULAR_MOSAIC, assess_queue_rectangle_science),
                               (QueueMosaicKind.SINGLE_FIELD, assess_single_field_science)):
            result = evaluate(parsed, request, proposed, nominal_conversion=options.nominal_conversion, prepared=prepared)
            from alma_duplicate.mosaic_spectral_evidence import attach_queue_spectral_setups
            attach_queue_spectral_setups(result, parsed)
            reports[kind.value] = result
            candidates = result['candidates']
            for candidate in candidates:
                if kind is not QueueMosaicKind.RECTANGULAR_MOSAIC:
                    represented.update(row['source_row_id'] for row in candidate['source_rows'])
                else:
                    represented[candidate['geometry']['source_row_id']] += 1
            counts[kind.value] = dict(evaluated=len(candidates), unresolved_by_intent={
                intent: sum(any(b['branch'] == intent and b['truth'] == 'UNKNOWN'
                                for b in c['science']['branches']) for c in candidates)
                for intent in request.intents})
        rows = []
        expected = Counter()
        for row in parsed.row_inputs:
            row_id = row.raw_row.row_id.value
            kind = row.spatial.mosaic_kind
            limitations = []
            if kind.value in reports:
                expected[row_id] += 1
            else:
                limitations.append('CANDIDATE_GEOMETRY_NOT_EVALUATED')
            if isinstance(row.spectral, SpectralScanEvidence):
                limitations.append('SPECTRAL_SCAN_NOT_EXPANDED')
            if (row.spatial.coordinate_system_raw or '').strip().lower() == 'galactic':
                limitations.append('GALACTIC_RECONSTRUCTION_UNSUPPORTED')
            rows.append(dict(source_row_id=row_id, geometry_kind=kind.value,
                             evaluated=kind.value in reports, limitations=limitations,
                             tp_treatment='IGNORED' if row.request.use_tp else 'NOT_REQUESTED'))
        if represented != expected:
            raise ValueError('Queue Mosaic candidate reports disagree with snapshot row inventory')
        report['inventory'] = dict(source_rows=rows, candidate_counts=counts,
                                   unevaluated_rows=sum(not r['evaluated'] for r in rows))
        status = AssessmentStatus.COMPLETED
    report['assessment_status'] = status.value
    return AssessmentResult(status, validated, report)
