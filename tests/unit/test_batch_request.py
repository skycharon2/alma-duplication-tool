"""Independent request identity, input isolation and redshift ownership."""
from copy import deepcopy

import pytest

from alma_duplicate.batch_request import build_batch_requests
from alma_duplicate.separated_setup_input import SEPARATED_OBSERVATION_CONTRACT
from tests.integration.test_separated_setup_contract_step03ba import new_wire

SOURCES = b'name,ra,dec,redshift\nsame,02:00:00,-00:30:00,0\nsame,30,-0.5,0.685\nmissing,0,90,\n'


@pytest.mark.parametrize('v2', [False, True])
def test_redshift_overrides_and_detached_children(v2):
    shared = new_wire()
    request = shared['request']
    request['source_redshift'] = '9'
    request['line_requirements'][0]['source_redshift'] = '8'
    if v2:
        request['line_input_contract'] = SEPARATED_OBSERVATION_CONTRACT
        request['continuum_requirement'] = {'source_redshift': '7', 'rms': {'value': '1', 'unit': 'mJy/beam'}}
    before = deepcopy(shared)
    batch = build_batch_requests(shared, SOURCES)
    assert shared == before
    assert [c['source']['source_id'] for c in batch['sources']] == ['line-2', 'line-3', 'line-4']
    for child, z in zip(batch['sources'], ['0', '0.685', None]):
        req = child['document']['request']
        assert req.get('source_redshift') == z
        assert 'source_redshift' not in req['line_requirements'][0]
        if v2:
            assert 'source_redshift' not in req['continuum_requirement']
        assert req['physical_spw_evidence'] == before['request']['physical_spw_evidence']
        assert child['document']['search_options'] == before['search_options']
    first = batch['sources'][0]['document']
    assert first['request']['position'] == dict(ra='02:00:00', dec='-00:30:00',
                                               ra_format='HMS', dec_format='DMS', frame='ICRS')
    first['request']['line_requirements'][0]['window_center']['value'] = '1'
    first['search_options']['sources'].clear()
    sibling = batch['sources'][1]['document']
    assert sibling['request']['line_requirements'][0]['window_center']['value'] == '225.1'
    assert sibling['search_options'] == before['search_options']
    assert shared == before


@pytest.mark.parametrize('change', [dict(target_kind='SUN'), dict(target_kind='MOVING'),
    dict(geometry='MOSAIC'), dict(line_input_contract='unknown'), dict(line_requirements='invalid')])
def test_unsupported_shared_input_is_not_silently_reinterpreted(change):
    shared = new_wire()
    shared['request'].update(change)
    with pytest.raises(ValueError):
        build_batch_requests(shared, SOURCES)


def test_invalid_source_prevents_partial_expansion():
    with pytest.raises(ValueError, match='row errors'):
        build_batch_requests(new_wire(), b'name,ra,dec\na,0,0\nb,360,0')


def test_separated_v1_retains_existing_execution_gate():
    from alma_duplicate.request_validation import validate_proposed_observation
    batch = build_batch_requests(new_wire(), SOURCES)
    for child in batch['sources']:
        document = child['document']
        result = validate_proposed_observation(document['request'], document['search_options'])
        assert not result.can_search
        assert any(i.code == 'SEPARATED_INPUT_NOT_EXECUTABLE' for i in result.issues)


@pytest.mark.parametrize('document', [None, {}, {'request': []}, {'request': {}, 'search_options': []}])
def test_document_shape_errors(document):
    with pytest.raises(ValueError):
        build_batch_requests(document, SOURCES)
