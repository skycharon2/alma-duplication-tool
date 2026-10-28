"""Separated LINE records in the existing Mosaic form."""
from dataclasses import replace

from alma_duplicate.domain.proposed_observation import SearchReadiness, RequestIssue
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
from alma_duplicate.separated_setup_input import SEPARATED_OBSERVATION_CONTRACT


def enabled(values):
    return (values.get('target_kind', 'FIXED') == 'FIXED'
            and values.get('geometry', 'SINGLE_POINTING') in {'MOSAIC', 'SINGLE_POINTING'}
            and bool(values.get('intents')) and not set(values.get('intents', [])) - {'LINE', 'CONTINUUM'}
            and (values.get('geometry') == 'MOSAIC' or values.get('sources') == ['ARCHIVE']))


def convert(document, values, rows, bindings):
    request = document['request']
    windows = request.pop('spectral_windows')
    sensitivities = request.pop('sensitivities')
    if 'CONTINUUM' in request['intents']:
        aggregate = next((s for s in sensitivities if s['purpose'] == 'CONTINUUM'), {})
        request['continuum_requirement'] = dict(rms=aggregate.get('rms'),
                                              physical_spw_ids=aggregate.get('window_ids', []))
        bindings['request.continuum_requirement.rms'] = 'aggregate'
        bindings['request.continuum_requirement.physical_spw_ids'] = 'aggregate_windows'
    complete = request.pop('setup_complete')
    requirements, evidence = [], []
    for i, (row, window) in enumerate(zip(rows, windows)):
        path = f'request.line_requirements[{i}]'
        item = dict(requirement_id=window['window_id'], window_center=window['center'],
                    correlator_mode=window['correlator_mode'])
        for key, suffix, unit in [('spectral_resolution', 'resolution', 'km/s'),
                                  ('rms', 'rms', 'mJy/beam')]:
            item[key] = {'value': values.get(row + '_' + suffix, ''),
                         'unit': values.get(row + '_' + suffix + '_unit', unit)}
            bindings[path + '.' + key] = row + '_' + suffix
        if values.get(row + '_redshift', '').strip():
            item['source_redshift'] = values[row + '_redshift']
        bindings[path] = row
        bindings[path + '.window_center'] = row + '_center'
        bindings[path + '.correlator_mode'] = row + '_mode'
        bindings[path + '.source_redshift'] = row + '_redshift'
        requirements.append(item)
        # Preserve bandwidth entered before the separated form was enabled.
        if window.get('bandwidth') is not None:
            evidence.append(dict(spw_id='physical-' + window['window_id'],
                linked_line_requirement_id=window['window_id'], bandwidth=window['bandwidth'],
                bandwidth_kind=window['bandwidth_kind']))
    for row in values.get('spw_rows', []):
        path = f'request.physical_spw_evidence[{len(evidence)}]'
        item = {'spw_id': values.get(row + '_id', row)}
        for key, suffix in [('linked_line_requirement_id', 'link')]:
            if values.get(row + '_' + suffix):
                item[key] = values[row + '_' + suffix]
            bindings[path + '.' + key] = row + '_' + suffix
        if values.get(row + '_bandwidth', '').strip():
            item.update(bandwidth={'value': values[row + '_bandwidth'],
                        'unit': values.get(row + '_bandwidth_unit', 'MHz')},
                        bandwidth_kind=values.get(row + '_bandwidth_kind', 'UNKNOWN'))
        bindings[path] = row
        bindings[path + '.bandwidth'] = row + '_bandwidth'
        evidence.append(item)
    request.update(line_input_contract=SEPARATED_OBSERVATION_CONTRACT,
                   line_requirements=requirements, physical_spw_evidence=evidence,
                   physical_spw_inventory_complete=complete)
    return document


def validate(document):
    result = validate_proposed_observation(document['request'], document['search_options'])
    issues = tuple(i for i in result.issues if i.code != 'SEPARATED_INPUT_NOT_EXECUTABLE')
    if document['request'].get('line_input_contract') != SEPARATED_OBSERVATION_CONTRACT:
        return result
    if any(i.category == 'ERROR' for i in issues):
        return replace(result, issues=issues, search_readiness=SearchReadiness.BLOCKED)
    try:
        prepared = prepare_submitted_line_request(document['request'])
        if prepared.line_request.geometry == 'SINGLE_POINTING':
            from alma_duplicate.submitted_line_assessment import _base_validation
            _base_validation(prepared, document['search_options'])
    except ValueError as exc:
        issue = RequestIssue('ERROR', 'LINE_INPUT_NOT_READY', 'request', str(exc))
        return replace(result, issues=issues + (issue,), search_readiness=SearchReadiness.BLOCKED)
    from alma_duplicate.ui.proposed import _continuum_inventory_errors
    issues += _continuum_inventory_errors(prepared.continuum_request)
    return replace(result, request=prepared.line_request, issues=issues,
                   search_readiness=SearchReadiness.BLOCKED if any(i.category == 'ERROR' for i in issues) else SearchReadiness.READY)
