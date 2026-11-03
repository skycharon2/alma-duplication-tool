"""Shared input contract for Queue Mosaic assessment adapters."""
from dataclasses import replace

from alma_duplicate.domain.proposed_observation import SearchReadiness
from alma_duplicate.reporting import json_value
from alma_duplicate.rules.continuum_setup import PORTAL_SCRIPT_V1
from alma_duplicate.rules.queue_mosaic_position import _points


def validate_inputs(validated, proposed, options, sources, report_detail):
    request = validated.request
    if request.target_kind != 'FIXED' or request.geometry != 'MOSAIC':
        raise ValueError('Queue Mosaic requires a fixed Mosaic request')
    request.require_implemented_line_scope()
    if validated.search_options.sources != ('QUEUE',):
        raise ValueError('Queue Mosaic assessment requires QUEUE only')
    if validated.search_options.predicates:
        raise ValueError('Queue Mosaic prefilter predicates are not implemented; omit them')
    if any(x is not None for x in (sources.archive_kind, sources.archive_provider,
                                   sources.archive_array_fetcher)):
        raise ValueError('Queue Mosaic does not accept Archive inputs')
    if (options.beam_decision_ref is not None or options.queue_candidate_beam
            or options.aq_equivalent_filters or options.queue_common
            or options.queue_continuum or options.queue_line):
        raise ValueError('Queue Mosaic selects complete science; omit Single Pointing flags')
    if options.nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError('Unknown proposed nominal bandwidth conversion')
    if report_detail != 'full':
        raise ValueError('Queue Mosaic currently requires full report detail')
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
    return validated


def load_snapshot(sources):
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
    return parsed, source
