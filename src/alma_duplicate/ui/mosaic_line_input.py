"""Explicit mapping of normal-form LINE rows to submitted requirements."""
from copy import deepcopy

from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
from alma_duplicate.separated_setup_input import SEPARATED_INPUT_CONTRACT


def is_mosaic_line(document):
    request = document['request']
    return (request.get('target_kind') == 'FIXED' and request.get('geometry') == 'MOSAIC'
            and request.get('intents') == ['LINE']
            and document['search_options'].get('sources') == ['ARCHIVE'])


def submitted_document(document):
    """Every explicit form window is a requirement; never infer roles from RMS."""
    if not is_mosaic_line(document):
        raise ValueError('Expected Archive-only Mosaic LINE form')
    result = deepcopy(document)
    request = result['request']
    windows = request.pop('spectral_windows')
    sensitivities = request.pop('sensitivities')
    complete = request.pop('setup_complete', False)
    requirements, evidence = [], []
    for window in windows:
        identifier = window['window_id']
        matches = [s for s in sensitivities if s.get('purpose') == 'LINE'
                   and s.get('scope') == 'WINDOW' and s.get('window_ids') == [identifier]]
        if len(matches) != 1:
            raise ValueError('Each requested LINE window requires one sensitivity record')
        sensitivity = matches[0]
        requirements.append(dict(requirement_id=identifier, window_center=window['center'],
            correlator_mode=window['correlator_mode'], rms=sensitivity.get('rms'),
            spectral_resolution=sensitivity.get('smoothing_resolution')))
        if window.get('bandwidth') is not None:
            evidence.append(dict(spw_id='physical-' + identifier,
                linked_line_requirement_id=identifier, center=window['center'],
                bandwidth=window['bandwidth'], bandwidth_kind=window['bandwidth_kind']))
    request.update(line_input_contract=SEPARATED_INPUT_CONTRACT,
        line_requirements=requirements, physical_spw_evidence=evidence,
        physical_spw_inventory_complete=complete)
    prepare_submitted_line_request(request)
    return result
