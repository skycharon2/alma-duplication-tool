"""Queue Custom application adapter; no single-point candidate prefilter."""
from dataclasses import replace

from alma_duplicate.domain.proposed_observation import SearchReadiness
from alma_duplicate.reporting import json_value
from alma_duplicate.queue_custom_backend import PROFILE
from alma_duplicate.queue_custom_science import assess_queue_custom_science
from alma_duplicate.rules.continuum_setup import PORTAL_SCRIPT_V1
from alma_duplicate.rules.queue_mosaic_position import _points


def assess_custom(validated, proposed, *, options, sources, input_sha256, report_detail, prepared=None):
    # Local import avoids an assessment -> adapter -> assessment import cycle.
    from alma_duplicate.assessment import AssessmentResult, AssessmentStatus

    request = validated.request
    if request.target_kind != 'FIXED' or request.geometry != 'MOSAIC':
        raise ValueError('Queue Custom requires a fixed Mosaic request')
    request.require_implemented_line_scope()
    if validated.search_options.sources != ('QUEUE',):
        raise ValueError('Queue Custom assessment requires QUEUE only')
    if validated.search_options.predicates:
        raise ValueError('Queue Custom prefilter predicates are not implemented; omit them')
    if any(x is not None for x in (sources.archive_kind, sources.archive_provider,
                                   sources.archive_array_fetcher)):
        raise ValueError('Queue Custom does not accept Archive inputs')
    if (options.beam_decision_ref is not None or options.queue_candidate_beam
            or options.aq_equivalent_filters or options.queue_common
            or options.queue_continuum or options.queue_line):
        raise ValueError('Queue Custom selects complete science; omit Single Pointing flags')
    if options.nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError('Unknown proposed nominal bandwidth conversion')
    if report_detail != 'full':
        raise ValueError('Queue Custom currently requires full report detail')
    if (not isinstance(proposed, dict) or proposed.get('source_name') != request.target_name
            or proposed.get('setup_id') != request.setup_id):
        raise ValueError('Proposed pointing list must bind to request target and setup')
    if proposed.get('frame_basis') != 'USER_CONFIRMED_FIXED_ICRS':
        raise ValueError('Confirmed fixed ICRS proposal required')
    _points(proposed.get('points'))
    validated = replace(validated, search_readiness=SearchReadiness.READY,
        issues=tuple(i for i in validated.issues if not
                     (i.category == 'CAPABILITY' and i.path == 'request'
                      and i.code == 'METHOD_NOT_IMPLEMENTED')))
    document = dict(schema_version='queue_custom_assessment_1', report_kind='QUEUE_CUSTOM_MOSAIC',
        input_sha256=input_sha256, source_mode='QUEUE_CSV',
        proposed=proposed, scientific_request=json_value(request.raw_input),
        evaluation_configuration=dict(profile=PROFILE, nominal_conversion=options.nominal_conversion,
            science_intents=list(request.intents), report_detail='full',
            candidate_selection='ALL_CUSTOM_GROUPS_IN_SNAPSHOT',
            single_point_radius_applied=False, result_limit_applied=False),
        discovery_scope='CUSTOM_GROUPS_ONLY_NOT_ALL_QUEUE_GEOMETRIES',
        duplication_status='NO_SEARCH_WIDE_ABSENCE_CLAIM', candidates=[])
    source = dict(status='NOT_PROVIDED', reasons=['QUEUE_CSV_NOT_PROVIDED'])
    parsed = None
    if sources.queue_loader is not None:
        try:
            parsed = sources.queue_loader()
        except (OSError, ValueError):
            source = dict(status='FAILED', reasons=['QUEUE_CSV_READ_FAILED'])
        else:
            source = dict(status='COMPLETE' if parsed.can_reconstruct else 'INCOMPLETE',
                parser_status=parsed.status, snapshot=json_value(parsed.snapshot),
                issues=json_value(parsed.issues), reasons=[] if parsed.can_reconstruct else
                ['QUEUE_SNAPSHOT_NOT_RECONSTRUCTABLE'])
    status = AssessmentStatus.SOURCES_UNAVAILABLE
    if parsed is not None and parsed.can_reconstruct:
        document.update(assess_queue_custom_science(parsed, request, proposed,
            nominal_conversion=options.nominal_conversion, prepared=prepared))
        document['science_schema_version'] = document['schema_version']
        document['schema_version'] = 'queue_custom_assessment_1'
        status = AssessmentStatus.COMPLETED
    document.update(assessment_status=status.value, sources={'QUEUE': source})
    return AssessmentResult(status, validated, document)


def assess_custom_submitted(raw_request, search_options, proposed, *, sources):
    """Reuse the browser's separated scientific operands without mixing inventories."""
    from alma_duplicate.assessment import AssessmentOptions
    from alma_duplicate.request_validation import validate_proposed_observation
    from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
    prepared = prepare_submitted_line_request(raw_request)
    validation = validate_proposed_observation(json_value(prepared.line_request.raw_input), search_options)
    if not validation.is_valid:
        raise ValueError('Invalid Queue Mosaic request/search options')
    validation = replace(validation, request=prepared.line_request)
    result = assess_custom(validation, proposed, options=AssessmentOptions(), sources=sources,
                           input_sha256=None, report_detail='full', prepared=prepared)
    result.document['scientific_request'] = json_value(raw_request)
    result.document['input_contract'] = prepared.input_contract
    result.document['line_scope'] = 'SUBMITTED_REQUIREMENTS_ONLY'
    return result
