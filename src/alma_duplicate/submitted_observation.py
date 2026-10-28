"""One fixed observation with separate LINE and continuum scientific inputs."""
from dataclasses import replace

from alma_duplicate.request_validation import _Validator, validate_proposed_observation
from alma_duplicate.separated_setup_input import (
    parse_separated_setup, SEPARATED_OBSERVATION_CONTRACT,
)
from alma_duplicate.rules.submitted_line_evaluation import PreparedSubmittedLineRequest, _SHARED_FIELDS
from alma_duplicate.proposed_frequency import prepare_frequency
from alma_duplicate.reporting import json_value


def prepare_observation(raw):
    v = _Validator()
    detached = v.snapshot(raw, 'request')
    separated = parse_separated_setup(v, detached)
    if any(i.category == 'ERROR' for i in v.issues) or separated is None:
        raise ValueError('; '.join(i.path + ': ' + i.message for i in v.issues))
    intents = tuple(detached.get('intents', ()))
    if (detached.get('target_kind') != 'FIXED' or not intents
            or set(intents) - {'LINE', 'CONTINUUM'}):
        raise ValueError('Select LINE, CONTINUUM, or both for a fixed observation')
    shared = {k: val for k, val in detached.items() if k in _SHARED_FIELDS}
    baseline = validate_proposed_observation(shared)
    if not baseline.is_valid or baseline.request is None:
        raise ValueError('Invalid target or angular inputs')
    base = baseline.request
    if base.angular_resolution is None:
        raise ValueError('Planned angular resolution is required')
    if base.geometry == 'SINGLE_POINTING' and base.position is None:
        raise ValueError('Single Pointing requires an ICRS position')
    if base.geometry == 'MOSAIC' and not base.target_name:
        raise ValueError('Mosaic requires a target name')
    continuum = None
    if 'CONTINUUM' in intents:
        item = v.obj(detached.get('continuum_requirement'), 'request.continuum_requirement',
                     {'rms', 'physical_spw_ids', 'source_redshift'})
        ids = item.get('physical_spw_ids', ())
        science = dict(shared, intents=['CONTINUUM'],
            setup_complete=separated.physical_inventory_complete,
            spectral_windows=[dict(window_id=w.window_id,
                center=None if w.center is None else dict(value=w.center.quantity.raw_value,
                    unit=w.center.quantity.raw_unit, kind=w.center.kind),
                bandwidth=None if w.bandwidth is None else dict(value=w.bandwidth.raw_value, unit=w.bandwidth.raw_unit),
                bandwidth_kind=w.bandwidth_kind) for w in separated.physical_spw_windows],
            sensitivities=[dict(sensitivity_id='continuum', purpose='CONTINUUM', scope='SETUP',
                setup_id=base.setup_id, basis='AGGREGATE', aggregate_path='DIRECT_DECLARATION',
                window_ids=json_value(ids), rms=json_value(item.get('rms')))])
        if 'source_redshift' in item:
            science['source_redshift'] = item['source_redshift']
        if detached.get('continuum_setup_declaration') is not None:
            science['continuum_setup_declaration'] = detached['continuum_setup_declaration']
        checked = validate_proposed_observation(science)
        if any(i.category == 'ERROR' for i in v.issues) or not checked.is_valid:
            raise ValueError('Invalid continuum requirement: ' + '; '.join(
                i.path + ': ' + i.message for i in (*v.issues, *checked.errors)))
        continuum = checked.request
        if (prepare_frequency(continuum.representative_frequency, continuum.source_redshift).sky_ghz is None
                or not continuum.sensitivities or continuum.sensitivities[0].rms is None):
            raise ValueError('Continuum requires a convertible representative frequency and aggregate RMS')
    elif detached.get('continuum_requirement') is not None:
        raise ValueError('Select CONTINUUM before submitting its scientific requirement')
    return PreparedSubmittedLineRequest(
        replace(base, spectral_windows=separated.line_windows,
                sensitivities=separated.line_sensitivities, setup_complete=None),
        separated, SEPARATED_OBSERVATION_CONTRACT, continuum)


def continuum_setup(prepared):
    if prepared.continuum_request is None:
        return None
    from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
    from alma_duplicate.rules.confirmed import approve_setup
    from alma_duplicate.assessment import PORTAL_SCRIPT_V1
    request = prepared.continuum_request
    conversion = (PORTAL_SCRIPT_V1 if request.continuum_setup_declaration is None
                  and any(w.bandwidth_kind == 'NOMINAL' or
                          (w.interval is not None and w.interval.kind == 'NOMINAL')
                          for w in request.spectral_windows) else None)
    return approve_setup(evaluate_continuum_setup(request, nominal_conversion=conversion),
                         nominal_conversion=conversion)


def continuum_context(prepared, context, common, *, mosaic=False):
    from alma_duplicate.rules.continuum import evaluate_continuum_frequency, evaluate_continuum_rms
    from alma_duplicate.rules.aggregation import aggregate_continuum
    request = prepared.continuum_request
    if request is None:
        return (), ()
    criteria = (evaluate_continuum_frequency(request, context), evaluate_continuum_rms(request, context))
    supported = not {'ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED',
                     'UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED',
                     'CONFLICTING_POSITION_INTERPRETATION'}.intersection(common[1].reasons)
    if not mosaic:
        supported = supported and context.evidence.prepared.normalized_metadata.is_mosaic.value is False
    branch = aggregate_continuum(context, (continuum_setup(prepared), *common, *criteria),
                                 supported=supported, mosaic=mosaic)
    return criteria, (branch,)
