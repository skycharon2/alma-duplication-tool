from unittest.mock import Mock

import pytest

from alma_duplicate.assessment import assess_observation, AssessmentSources
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_queue_custom_science import candidate as custom, request
from tests.integration.test_queue_rectangle_science import candidate as rectangle


def run(parsed, changes=None):
    _, payload = request()
    payload['request']['geometry'] = 'SINGLE_POINTING'
    payload['request'].update(changes or {})
    payload['search_options']['sources'] = ['QUEUE']
    loader = Mock(return_value=parsed)
    result = assess_observation(**payload, queue_single_mosaics=True,
                               sources=AssessmentSources(queue_loader=loader))
    loader.assert_called_once_with()
    assert result.document is not None, result.validation.issues
    return result.document


@pytest.mark.parametrize('factory,kind', [(custom, 'CUSTOM'), (rectangle, 'RECTANGLE')])
@pytest.mark.parametrize('changes,truth', [({}, 'TRUE'), ({'Ref.Frequency': '100'}, 'FALSE'),
    ({'Mos. Coord.': 'galactic'}, 'UNKNOWN')])
def test_science_and_provenance(factory, kind, changes, truth):
    report = run(factory(changes))['geometry_reports'][kind]
    for c in report['candidates']:
        assert c['science']['branches'][0]['truth'] == truth
        assert c['science']['branches'][0]['required_criteria'][0] == 'POS-SINGLE'
        assert c['position']['threshold'] == 'POINT_WITHIN_CANDIDATE_BEAM_UNION'
        for v in c['science']['variants']:
            assert {r['criterion_id'] for r in v['criteria']} >= {'POS-SINGLE', 'ANGULAR'}


def test_mixed_snapshot_and_single_fields_explicitly_outside_increment():
    rows = [dict(zip(r.raw_row.declared_columns, r.raw_row.raw_values))
            for parsed in (custom(), rectangle()) for r in parsed.row_inputs]
    result = run(queue_rows(*rows, {'Mosaic': ''}))
    assert result['inventory']['evaluated_source_rows'] == 4
    assert result['inventory']['unevaluated_source_rows'] == 1
    assert len(result['geometry_reports']['CUSTOM']['candidates']) == 1
    assert len(result['geometry_reports']['RECTANGLE']['candidates']) == 2
    assert result['search_completeness'] == 'NOT_ESTABLISHED'


def test_array_branches_remain_independent_at_single_point():
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    offset = (primary_beam_fwhm_deg(230, 7) + primary_beam_fwhm_deg(230, 12))*900
    report = run(custom({'Lat Offset': str(offset), 'Long Offset': '0'}))
    c = report['geometry_reports']['CUSTOM']['candidates'][0]
    assert c['science']['matching_arrays_by_intent']['CONTINUUM'] == [7.]
    assert [v['outcome'] for v in c['position']['beam_variants']] == ['SATISFIED', 'NOT_SATISFIED']


@pytest.mark.parametrize('factor,outcome', [(1.001, 'NOT_SATISFIED'),
                                           (.999, 'SATISFIED')])
def test_single_point_boundary(factor, outcome):
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    radius = primary_beam_fwhm_deg(230,12)*1800
    c = run(custom({'Use 7-m?': 'False', 'Lat Offset': str(radius*factor),
                    'Long Offset': '0'}))['geometry_reports']['CUSTOM']['candidates'][0]
    assert c['position']['beam_variants'][0]['outcome'] == outcome


def test_full_line_branch_keeps_proposed_geometry():
    from dataclasses import replace
    from alma_duplicate.queue_single_mosaic_assessment import assess_single_mosaics
    from alma_duplicate.assessment import AssessmentOptions
    from alma_duplicate.request_validation import validate_proposed_observation
    from tests.integration.test_queue_custom_science import line_request
    _, payload = request()
    payload['request']['geometry'] = 'SINGLE_POINTING'
    payload['search_options']['sources'] = ['QUEUE']
    validated = validate_proposed_observation(payload['request'], payload['search_options'])
    req = replace(line_request(center_ghz=226., resolution_kms=20),
                  position=validated.request.position)
    validated = replace(validated, request=req)
    result = assess_single_mosaics(validated, options=AssessmentOptions(),
        sources=AssessmentSources(queue_loader=lambda:custom({'Project Code':'2024.1.00001.S',
            'Polarization':'DOUBLE','Req.Sensitivity':'0.001','Spec.Res. SPW 1':'0.9765625'})),
        input_sha256=None,report_detail='full')
    c=result.document['geometry_reports']['CUSTOM']['candidates'][0]
    assert c['science']['matching_arrays_by_intent']['LINE']==[7.,12.]
    assert result.validation.request.geometry=='SINGLE_POINTING'
    for v in c['science']['variants']:
        assert v['branches'][0]['required_criteria'][0]=='POS-SINGLE'


def test_exact_radius_is_inclusive(monkeypatch):
    import alma_duplicate.queue_single_mosaic_assessment as adapter
    original = adapter.assess_queue_custom_csv

    def exact_boundary(*args, **kwargs):
        report = original(*args, **kwargs)
        for c in report['candidates']:
            for v in c['position']['beam_variants']:
                for relation in v['points'][0]['relations']:
                    relation['separation_arcsec'] = v['radius_arcsec']
                    relation['boundary_delta_arcsec'] = 0
        return report

    monkeypatch.setattr(adapter, 'assess_queue_custom_csv', exact_boundary)
    c = run(custom())['geometry_reports']['CUSTOM']['candidates'][0]
    assert all(v['outcome'] == 'SATISFIED' for v in c['position']['beam_variants'])
    assert all(v['counts']['INSIDE'] == 1 for v in c['position']['beam_variants'])
