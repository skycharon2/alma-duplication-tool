"""Handwritten-workflow examples projected from real backend reports."""

from copy import deepcopy
import json

import pytest

from alma_duplicate.reporting import report_document, report_json_text
from alma_duplicate.ui import create_app
from alma_duplicate.ui.calculation_view import calculation_view, line_preparation
from alma_duplicate.ui.report_view import criterion_view
from tests.integration.test_line_preparation import report
from tests.integration.test_queue_continuum import case


def serialized(evaluation):
    return json.loads(report_json_text(report_document(evaluation)))


def test_archive_notes_example_keeps_preparation_and_rms_stages():
    document = serialized(report())
    original = deepcopy(document)
    pair = document['context_evaluations'][0]['line_pairs'][0]
    facts = {f['label']: f for f in line_preparation(pair, document['request'])}
    assert facts['Entered centre frequency']['value'] == 230.538
    assert facts['Source redshift']['value'] == 0.024
    assert facts['Prepared sky frequency']['value'] == 225.134765625
    assert facts['Entered planned RMS']['unit'] == 'mJy/beam'
    rms = next(r for r in pair['criteria'] if r['criterion_id'] == 'LINE-RMS')
    steps = calculation_view(rms)
    facts = {f['label']: f for f in steps['facts']}
    assert facts['Archive RMS at planned resolution']['value'] == pytest.approx(0.282842712474619)
    assert facts['Archive RMS after angular correction']['value'] == pytest.approx(0.4072935059634514)
    assert document == original


@pytest.mark.parametrize('overlap, bandwidth', [(False, 3750), (True, 937.5)])
def test_queue_usable_union_and_rms_use_backend_operands(overlap, bandwidth):
    changes = {'Req.Sensitivity': '2', 'Ref.Freq.Width': '100'}
    changes.update({f'Bandwidth SPW {n}': '1000' for n in range(1, 5)})
    if overlap:
        changes.update({f'Freq SPW {n}': '230' for n in range(1, 5)})
    _, evaluation, _ = case(changes, rms=1)
    document = serialized(evaluation)
    record = next(r for r in document['context_evaluations'][0]['criteria'] if r['criterion_id'] == 'CONT-RMS')
    before = deepcopy(record)
    steps = calculation_view(record)
    facts = {f['label']: f['value'] for f in steps['facts']}
    assert facts['Queue aggregate usable bandwidth'] == bandwidth
    assert len(steps['windows']) == 4
    assert all(w['nominal_bandwidth_mhz'] == 1000 and w['usable_bandwidth_ghz'] == .9375 for w in steps['windows'])
    assert criterion_view(record)['candidate']['value'] == pytest.approx(2 * (100 / bandwidth) ** .5)
    assert record['candidate']['value'] == 2
    assert record == before


def test_missing_aggregate_is_not_replaced_with_reference_rms():
    r = {'criterion_id': 'CONT-RMS', 'candidate': {'value': 12, 'unit': 'mJy'},
         'derived': [['aggregate_rms_mjy', None]],
         'details': [['spw_evidence_json', 'invalid'], ['aggregate_bandwidth_complete', 'False']]}
    assert criterion_view(r)['candidate']['value'] is None
    assert calculation_view(r)['windows'] == []
    assert 'partial bandwidth' in calculation_view(r)['notes'][-1]


def test_preparation_never_borrows_another_window_or_ambiguous_sensitivity():
    document = serialized(report())
    pair = document['context_evaluations'][0]['line_pairs'][0]
    raw = document['request']['raw']
    raw['sensitivities'].append(deepcopy(raw['sensitivities'][0]))
    assert 'Entered planned RMS' not in {f['label'] for f in line_preparation(pair, document['request'])}
    raw['spectral_windows'][0]['window_id'] = 'different-line'
    assert 'Entered centre frequency' not in {f['label'] for f in line_preparation(pair, document['request'])}
    assert line_preparation({}, {})[-1]['value'] is None


def test_report_page_shows_readable_steps_and_keeps_original_download(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **k: pytest.fail('report presentation must not query sources'))
    document = serialized(report())
    document['request']['raw']['spectral_windows'][0]['center']['kind'] = '<script>bad</script>'
    directory = tmp_path / 'line'
    directory.mkdir()
    raw = report_json_text(document).encode()
    (directory / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    html = client.get('/reports/1').get_data(as_text=True)
    readable = html.split('<details id="technical-records"')[0]
    assert 'How this comparison was made' in readable
    assert 'Archive RMS at planned resolution' in readable
    assert '0.282843' in readable and '0.407294' in readable
    assert 'Prepared sky frequency' in readable and '225.135' in readable
    assert '<script>bad</script>' not in html
    assert '&lt;script&gt;bad&lt;/script&gt;' in readable
    assert client.get('/reports/1/download/report').data == raw


def test_queue_line_shows_distinct_reference_width_and_resolution():
    # Stored backend operands deliberately disagree: a presenter must not repair
    # them, recalculate the result, or relabel Queue mJy as mJy/beam.
    record = {'criterion_id': 'LINE-RMS', 'candidate': {'value': 1, 'unit': 'mJy'},
              'derived': [['planned_resolution_mhz', .3836], ['queue_reference_width_mhz', .325],
                          ['queue_rms_at_planned_resolution_mjy', .9204],
                          ['comparable_queue_rms_mjy', 999], ['theta_plan_arcsec', .5],
                          ['theta_queue_arcsec', .6]]}
    facts = {f['label']: f for f in calculation_view(record)['facts']}
    assert facts['Queue reference noise bandwidth']['value'] == .325
    assert facts['Planned spectral resolution at the line frequency']['value'] == .3836
    assert criterion_view(record)['candidate'] == {
        'value': 999, 'unit': 'mJy',
        'semantics': 'At the requested spectral resolution and backend angular comparison basis'}


@pytest.mark.parametrize('value', [None, 'null', '{}', '[null, 3, "text"]'])
def test_legacy_missing_or_unrecognized_window_evidence(value):
    assert calculation_view({'criterion_id': 'CONT-RMS',
                             'derived': [['aggregate_rms_mjy', None]],
                             'details': [['spw_evidence_json', value]]})['windows'] == []
