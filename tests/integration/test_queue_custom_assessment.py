"""Unified entrypoint retains Custom scope, lazy inputs and full array branches."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from alma_duplicate.assessment import assess_observation, AssessmentSources, AssessmentOptions
from alma_duplicate.cli.evaluate import main
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from tests.integration.test_queue_custom_science import candidate, request, pointings, science


def run(parsed=None, proposed=None, **kwargs):
    req, payload = request()
    payload['search_options']['sources'] = ['QUEUE']
    return assess_observation(**payload, queue_custom=proposed or pointings(req),
        sources=kwargs.pop('sources', AssessmentSources(queue_loader=lambda: parsed or candidate())), **kwargs)


@pytest.mark.parametrize('changes,diameters', [({}, [7., 12.]),
    ({'Use 7-m?':'False'}, [12.]), ({'Req. Ang. Res.':'20'}, [7.])])
def test_array_branches_survive_unified_entry(changes, diameters):
    result = run(candidate(changes))
    assert result.status == 'COMPLETED'
    assert result.validation.can_search
    d = result.document
    assert d['schema_version'] == 'queue_custom_assessment_1'
    assert [v['diameter_m'] for v in science(d)['variants']] == diameters
    assert d['sources']['QUEUE']['status'] == 'COMPLETE'
    assert d['evaluation_configuration']['result_limit_applied'] is False
    assert d['candidates'][0]['source_rows']
    json.dumps(d, allow_nan=False)


def test_only_7m_match_is_preserved():
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    req, _ = request()
    p = pointings(req)
    p['points'][0]['dec_deg'] += sum(primary_beam_fwhm_deg(230, d)/2 for d in (7, 12))/2
    s = science(run(proposed=p).document)
    assert [v['branches'][0]['truth'] for v in s['variants']] == ['TRUE', 'FALSE']
    assert s['matching_arrays_by_intent']['CONTINUUM'] == [7.]


def forbidden():
    pytest.fail('source must not be loaded')


@pytest.mark.parametrize('extra', [dict(report_detail='matches'),
    dict(options=AssessmentOptions(queue_continuum=True)), dict(mosaic=object())])
def test_invalid_configuration_fails_before_loading(extra):
    with pytest.raises(ValueError):
        run(sources=AssessmentSources(queue_loader=forbidden), **extra)


def test_invalid_and_solar_requests_never_load_queue():
    result = assess_observation({'target_kind':'INVALID'}, {}, queue_custom={},
        sources=AssessmentSources(queue_loader=forbidden))
    assert result.status == 'REQUEST_NOT_SEARCH_READY'
    result = assess_observation(dict(target_kind='SUN', geometry='SINGLE_POINTING',
        setup_id='sun', intents=['CONTINUUM']), {}, queue_custom={},
        sources=AssessmentSources(queue_loader=forbidden))
    assert result.status == 'SOLAR_EXEMPTION'


@pytest.mark.parametrize('kind', ['missing', 'failed', 'invalid_csv'])
def test_unavailable_source_is_not_empty_success(kind):
    def fail():
        raise OSError('unreadable')
    loader = {'missing':None, 'failed':fail,
              'invalid_csv':lambda: parse_queue_csv_bytes(b'invalid\n')}[kind]
    result = run(sources=AssessmentSources(queue_loader=loader))
    assert result.status == 'SOURCES_UNAVAILABLE'
    assert result.document['candidates'] == []
    assert result.document['sources']['QUEUE']['status'] != 'COMPLETE'


def test_does_not_truncate_snapshot_or_apply_single_point_radius():
    req, payload = request()
    payload['search_options'].update(sources=['QUEUE'], result_limit=1,
                                     radius={'value':.001, 'unit':'arcsec'})
    parsed = candidate()
    # Different source groups must both remain in the report despite result_limit=1.
    from tests.integration.test_candidate_search import queue_rows
    rows = [dict(zip(r.raw_row.declared_columns, r.raw_row.raw_values)) for r in parsed.row_inputs]
    parsed = queue_rows(*rows, *[r | {'Target Name':'other'} for r in rows])
    result = assess_observation(**payload, queue_custom=pointings(req),
        sources=AssessmentSources(queue_loader=lambda: parsed))
    assert len(result.document['candidates']) == 2


def test_cli_calls_unified_backend_and_protects_inputs(tmp_path):
    root = Path(__file__).resolve().parents[2]
    example = root/'examples/queue-custom-check'
    output = tmp_path/'report.json'
    args = ['--request', str(example/'request.json'), '--queue-custom-pointings',
        str(example/'proposed.json'), '--queue-csv',
        str(root/'examples/queue-mosaic-ot/custom-engineering.csv'), '--output', str(output)]
    assert main(args) == 0
    d = json.loads(output.read_text())
    assert d['report_kind'] == 'QUEUE_CUSTOM_MOSAIC'
    assert d['summary']['matching_candidates_by_intent']['CONTINUUM'] == 1
    assert main(args) == 2
    assert main(args[:-1]+[str(example/'proposed.json'), '--overwrite']) == 2


def test_complementary_array_criteria_do_not_become_match(monkeypatch):
    import alma_duplicate.queue_custom_science as backend
    from alma_duplicate.rules.model import CriterionOutcome as O
    original = backend.evaluate_queue_continuum
    def complementary(request, context, common, **kwargs):
        frequency, rms = original(request, context, common, **kwargs)
        diameter = dict(common[1].derived)['antenna_diameter_m']
        return (replace(frequency, outcome=O.SATISFIED if diameter == 7 else O.NOT_SATISFIED),
                replace(rms, outcome=O.NOT_SATISFIED if diameter == 7 else O.SATISFIED))
    monkeypatch.setattr(backend, 'evaluate_queue_continuum', complementary)
    s = science(run().document)
    assert [v['branches'][0]['truth'] for v in s['variants']] == ['FALSE', 'FALSE']
    assert s['matching_arrays_by_intent']['CONTINUUM'] == []


@pytest.mark.parametrize('mode', ['archive', 'predicates', 'wrong_target'])
def test_rejects_unsupported_scope_before_loading(mode):
    req, payload = request()
    payload['search_options']['sources'] = ['QUEUE']
    p = pointings(req)
    if mode == 'archive':
        payload['search_options']['sources'].append('ARCHIVE')
    elif mode == 'predicates':
        payload['search_options']['predicates'] = [dict(field='frequency', operator='=',
            quantity=dict(value=100, unit='GHz'))]
    else:
        p['source_name'] = 'other'
    with pytest.raises(ValueError):
        assess_observation(**payload, queue_custom=p, sources=AssessmentSources(queue_loader=forbidden))


def test_line_request_reaches_same_pair_science():
    from tests.integration.test_queue_line_evaluation import request as line_request
    from alma_duplicate.reporting import json_value
    req = line_request(center_ghz=226., resolution_kms=20)
    raw = json_value(req.raw_input)
    raw['geometry'] = 'MOSAIC'
    _, payload = request()
    payload['search_options']['sources'] = ['QUEUE']
    parsed = candidate({'Project Code':'2024.1.00001.S', 'Polarization':'DOUBLE',
                        'Req.Sensitivity':'0.001', 'Spec.Res. SPW 1':'0.9765625'})
    result = assess_observation(raw, payload['search_options'], queue_custom=pointings(req),
        sources=AssessmentSources(queue_loader=lambda: parsed))
    assert result.status == 'COMPLETED'
    assert science(result.document)['matching_arrays_by_intent']['LINE'] == [7., 12.]


def test_rectangle_is_reported_as_excluded():
    result = run(candidate({'Mosaic':'Rectangle'}))
    assert result.status == 'COMPLETED'
    assert result.document['candidates'] == []
    assert result.document['excluded_mosaic_candidates']
    assert all(c['reason'] == 'RECTANGLE_GRID_NOT_IMPLEMENTED'
               for c in result.document['excluded_mosaic_candidates'])
    assert result.document['duplication_status'].endswith('NO_SEARCH_WIDE_ABSENCE_CLAIM')


def test_partial_centers_keep_known_coverage_and_complete_science():
    from tests.integration.test_candidate_search import queue_rows
    rows = [dict(zip(r.declared_columns, r.raw_values)) for r in candidate().raw_rows]
    rows[1]['Long Offset'] = '324001'
    result = run(queue_rows(*rows))
    c = result.document['candidates'][0]
    assert c['science']['matching_arrays_by_intent']['CONTINUUM'] == [7., 12.]
    for v in c['position']['beam_variants']:
        assert v['outcome'] == 'SATISFIED'
        assert len(v['coverage']['points']) == 1
        assert len(v['coverage']['source_row_ids']) == 2
        assert v['coverage']['complete'] is False
        assert 'CUSTOM_CSV_COORDINATES_PARTIALLY_UNRESOLVED' in v['reasons']
    req, _ = request()
    outside = run(queue_rows(*rows), proposed=pointings(req, ra=0))
    assert all(v['outcome'] == 'UNKNOWN'
               for v in outside.document['candidates'][0]['position']['beam_variants'])


def test_invalid_candidate_beam_does_not_abort_healthy_candidate():
    from tests.integration.test_candidate_search import queue_rows
    rows = [dict(zip(r.declared_columns, r.raw_values)) for r in candidate().raw_rows]
    parsed = queue_rows(*rows, *[r | {'Target Name':'invalid-beam',
                                    'Ref.Frequency':'0.000000001'} for r in rows])
    result = run(parsed)
    assert result.status == 'COMPLETED'
    assert result.document['summary']['matching_candidates_by_intent']['CONTINUUM'] == 1
    broken = next(c for c in result.document['candidates'] if c['frequency']['value_ghz'] < 1)
    assert all(v['outcome'] == 'UNKNOWN' and 'CANDIDATE_BEAM_UNREPRESENTABLE' in v['reasons']
               for v in broken['position']['beam_variants'])
