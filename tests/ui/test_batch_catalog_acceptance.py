"""Catalog-backed HTTP workflow parity, not independent scientific acceptance."""
import csv
from io import BytesIO, StringIO
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.acceptance import load_catalog
from alma_duplicate.ui import create_app
from alma_duplicate.ui.runs import BrowserAssessment
from tests.ui.test_batch_routes import hidden
from tests.ui.test_cli_parity import form_for, normalized_times

CATALOG = Path(__file__).resolve().parents[2] / 'examples/acceptance/catalog.json'
CASES = ('ngc6240-line-diagnostic', 'ngc6240-continuum',
         'dual-source-line', 'dual-source-continuum')


@pytest.fixture(params=CASES)
def case_client(request, monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **k: pytest.fail('Acceptance must remain offline'))
    # Includes checksums for captured responses, not just catalog filenames.
    _, catalog = load_catalog(CATALOG)
    case, inputs, _ = next(item for item in catalog if item[0]['case_id'] == request.param)
    app = create_app(dict(
        TESTING=True, AUTO_QUEUE=False, REPORT_DIRECTORY=None,
        OFFLINE_ARCHIVE_REPLAY=inputs.get('archive_replay'),
        OFFLINE_QUEUE_CSV=inputs.get('queue_csv'), MANAGED_QUEUE_ROOT=None,
        ARCHIVE_ARRAY_EVIDENCE=None, LIVE_ARCHIVE=False, LIVE_AQ=False,
        SUBMITTED_LINE_V2_UI_ENABLED=False))
    try:
        yield app.test_client(), case, json.loads(inputs['request'].read_bytes())
    finally:
        app.extensions['assessment_runs'].close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()


@pytest.mark.parametrize('format', ['csv', 'txt'])
def test_catalog_upload_validate_run_and_standalone_exports(case_client, monkeypatch, format):
    client, case, document = case_client
    data = form_for(document)
    data['target_kind'] = 'FIXED'
    data['geometry'] = 'SINGLE_POINTING'
    # The two rows deliberately retain the captured cone. Their distinct names
    # and redshifts exercise identity and REST conversion, not two real proposals.
    sources = [(case['case_id'] + '-A', data['ra'], data['dec'], '0.024'),
               (case['case_id'] + '-B', data['ra'], data['dec'], '0')]
    stream = StringIO()
    writer = csv.writer(stream, delimiter=',' if format == 'csv' else ' ')
    writer.writerow(['name', 'ra', 'dec', 'redshift'])
    writer.writerows(sources)
    initial = client.get('/proposed/batch')
    data.update(dict(batch_csrf=hidden(initial, 'batch_csrf'),
                submission_token=hidden(initial, 'submission_token'),
                source_format=format))
    upload = data.copy()
    upload['action'] = 'preview-sources'
    upload['source_list'] = (BytesIO(stream.getvalue().encode()), 'targets.' + format)
    with monkeypatch.context() as offline:
        offline.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Preflight executed'))
        offline.setattr(BrowserAssessment, 'pin_queue_for_submission',
                        lambda *a: pytest.fail('Preflight accessed Queue'))
        preview = client.post('/proposed/batch', data=upload)
        assert preview.status_code == 200 and b'2 targets' in preview.data, preview.text
        data['source_upload_token'] = hidden(preview, 'source_upload_token')
        data['submission_token'] = hidden(preview, 'submission_token')
        data['action'] = 'validate'
        validation = client.post('/proposed/batch', data=data)
        assert b'All targets ready: <strong>Yes' in validation.data

    pin = BrowserAssessment.pin_queue_for_submission
    pinned = {}

    def same_snapshot(runner, selected):
        key = (runner, selected)
        if key not in pinned:
            pinned[key] = pin(runner, selected)
        return pinned[key]

    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', same_snapshot)
    data['action'] = 'assess'
    result = client.post('/proposed/batch', data=data)
    assert result.status_code == 303, result.text
    manifest = client.get(result.location + '/download/manifest').json
    assert manifest['execution_complete'] and len(manifest['sources']) == 2
    for source, expected in zip(manifest['sources'], sources):
        assert source['source']['name'] == expected[0]
        for branch in source['reports']:
            assert branch['availability'] == 'AVAILABLE'
            batch_url = '/runs/' + branch['run_id']
            # Independently fill the original Single Pointing form. Do not copy
            # a generated child request as the standalone input oracle.
            single = form_for(document)
            for key, value in dict(target_name=expected[0], ra=expected[1], dec=expected[2],
                                   redshift=expected[3], action='assess').items():
                single[key] = value
            single.setlist('intents', [branch['purpose']])
            standalone = client.post('/proposed', data=single)
            assert standalone.status_code == 303, standalone.text
            for kind in ('request', 'report', 'inspection'):
                batch_response = client.get(batch_url + '/download/' + kind)
                direct_response = client.get(standalone.location + '/download/' + kind)
                assert batch_response.status_code == direct_response.status_code == 200
                actual, expected_document = json.loads(batch_response.data), json.loads(direct_response.data)
                if kind == 'report':
                    assert actual['context_evaluations']
                    assert all(s['status'] == 'COMPLETED' for s in actual['sources'].values())
                    actual, expected_document = normalized_times(actual), normalized_times(expected_document)
                assert actual == expected_document, (case['case_id'], source['source_id'], branch['purpose'], kind)
            assert client.get(batch_url + '/visualization').status_code == 200
    # A repeated submit returns the same batch rather than starting more work.
    assert len(pinned) == 1, 'Batch and standalone must share exactly one source configuration'
    with monkeypatch.context() as no_repeat:
        no_repeat.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Duplicate execution'))
        assert client.post('/proposed/batch', data=data).location == result.location
