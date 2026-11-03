"""Queue Rectangle application adapter; no single-point candidate prefilter."""

from alma_duplicate.queue_mosaic_inputs import load_snapshot, validate_inputs
from alma_duplicate.reporting import json_value
from alma_duplicate.queue_rectangle_backend import PROFILE
from alma_duplicate.queue_rectangle_science import assess_queue_rectangle_science


def assess_rectangle(validated, proposed, *, options, sources, input_sha256, report_detail, prepared=None):
    # Local import avoids an assessment -> adapter -> assessment import cycle.
    from alma_duplicate.assessment import AssessmentResult, AssessmentStatus

    validated = validate_inputs(validated, proposed, options, sources, report_detail)
    request = validated.request
    document = dict(schema_version='queue_rectangle_assessment_1', report_kind='QUEUE_RECTANGLE_MOSAIC',
        input_sha256=input_sha256, source_mode='QUEUE_CSV',
        proposed=proposed, scientific_request=json_value(request.raw_input),
        evaluation_configuration=dict(profile=PROFILE, nominal_conversion=options.nominal_conversion,
            science_intents=list(request.intents), report_detail='full',
            candidate_selection='ALL_RECTANGLE_SOURCE_ROWS_IN_SNAPSHOT',
            single_point_radius_applied=False, result_limit_applied=False),
        discovery_scope='RECTANGLE_ROWS_ONLY_NOT_ALL_QUEUE_GEOMETRIES',
        duplication_status='NO_SEARCH_WIDE_ABSENCE_CLAIM', candidates=[])
    parsed, source = load_snapshot(sources)
    status = AssessmentStatus.SOURCES_UNAVAILABLE
    if parsed is not None and parsed.can_reconstruct:
        document.update(assess_queue_rectangle_science(parsed, request, proposed,
            nominal_conversion=options.nominal_conversion, prepared=prepared))
        document['science_schema_version'] = document['schema_version']
        document['schema_version'] = 'queue_rectangle_assessment_1'
        status = AssessmentStatus.COMPLETED
    document.update(assessment_status=status.value, sources={'QUEUE': source})
    return AssessmentResult(status, validated, document)
