"""Anonymous browser report access survives a restart and stays private."""
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from alma_duplicate.persistence.models import assessment_input_links
from alma_duplicate.ui import create_app
from alma_duplicate.ui.input_snapshot import restore_input_snapshot
from alma_duplicate.ui.runs import BrowserAssessment
from tests.persistence.test_foundation import config as migration_config
from tests.ui.test_batch_routes import hidden, upload
from tests.ui.test_mosaic_ot_preview import OT
from tests.ui.test_queue_custom_mosaic import form, submit
from tests.ui.test_runs import config


@pytest.fixture(params=['sqlite', 'postgresql'])
def database(tmp_path, request):
    if request.param == 'sqlite':
        yield 'sqlite:///' + str(tmp_path / 'browser.sqlite'), {}
        return
    url = os.environ.get('ALMA_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set ALMA_TEST_DATABASE_URL for PostgreSQL integration tests')
    admin = create_engine(url)
    schema = 'test_browser_' + uuid4().hex
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        yield url, {'connect_args': {'options': f'-csearch_path={schema}'}}
    finally:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.mark.parametrize('source_format,source_bytes', [
    ('csv', (Path(__file__).parents[1] / 'fixtures/source_list/five_targets.csv').read_bytes()),
    ('txt', b'name ra dec redshift\r\nfirst 201.365 -43.019 0.024\r\nsecond 201.365 -43.019 0\r\n'),
])
def test_reports_and_completed_batches_survive_browser_app_restart(tmp_path, database,
                                                                    source_format, source_bytes, monkeypatch):
    url, options = database
    engine = create_engine(url, **options)
    with engine.begin() as connection:
        command.upgrade(migration_config(connection), 'head')

    def start(engine):
        return create_app(config() | {
            'REPORT_STORAGE': 'database',
            'BROWSER_SESSION_SECRET': 'test-only-browser-signing-key-32-characters',
            'BROWSER_COOKIE_SECURE': False,
            'BROWSER_TEST_ENGINE': engine,
            'ARTIFACT_ROOT': str(tmp_path / 'artifacts'),
            'BATCH_MAX_WORKERS': 2,
        })

    def close(app):
        for key in ('assessment_runs', 'source_uploads', 'mosaic_uploads', 'assessment_drafts'):
            app.extensions[key].close()

    def saved_input(client, method, url):
        cookie = client.get_cookie('alma_browser_reports')
        with app.test_request_context('/reports', headers={'Cookie': f'{cookie.key}={cookie.value}'}):
            app.preprocess_request()
            runs = app.extensions['assessment_runs']
            return getattr(runs, method)(url.rsplit('/', 1)[-1])

    app = start(engine)
    try:
        owner = app.test_client()
        form_data = form(version='1' if source_format == 'csv' else '2')
        form_data['geometry'] = 'SINGLE_POINTING'
        form_data.update(dict(ra='201.365', dec='-43.019', action='assess'))
        assert owner.post('/proposed', data=form_data,
                          headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        single = owner.post('/proposed', data=form_data)
        assert single.status_code == 303, single.text
        mosaic_form = form()
        mosaic_form['mosaic_array'] = '7m'
        mosaic_form['mosaic_complete'] = 'on'
        mosaic_form['mosaic_fixed_icrs'] = 'on'
        mosaic = submit(owner, mosaic_form)
        assert mosaic.status_code == 303, mosaic.text
        _, data = upload(owner, raw=source_bytes, format=source_format)
        batch = owner.post('/proposed/batch', data=data | {'action': 'assess'})
        assert batch.status_code == 303, batch.text
        manifest_url = batch.location + '/download/manifest'
        manifest = owner.get(manifest_url).json
        batch_runs = [r['run_id'] for s in manifest['sources'] for r in s['reports']]
        assert len(batch_runs) == 2 * len(manifest['sources']) and all(batch_runs)
        batch_report = '/runs/' + batch_runs[0]
        download = owner.get(single.location + '/download/report').data
        cookie = owner.get_cookie('alma_browser_reports')
        assert cookie and cookie.http_only and cookie.expires
    finally:
        close(app)
        engine.dispose()

    engine = create_engine(url, **options)
    app = start(engine)
    try:
        owner, visitor = app.test_client(), app.test_client()
        owner.set_cookie('alma_browser_reports', cookie.value)
        assert owner.get(single.location).status_code == 200
        assert owner.get(single.location + '/download/report').data == download
        assert owner.get(batch.location).status_code == 200
        assert owner.get(manifest_url).json == manifest
        assert 'Back to batch overview' in owner.get(batch_report).text
        assert owner.get(batch_report + '/visualization').status_code == 200
        single_input = saved_input(owner, 'input_for_report', single.location)
        assert single_input['upload'] is None
        assert restore_input_snapshot(single_input['snapshot']).values['ra'] == '201.365'
        mosaic_input = saved_input(owner, 'input_for_report', mosaic.location)
        assert mosaic_input['snapshot']['workflow'] == 'MOSAIC'
        assert mosaic_input['upload']['raw'] == OT
        assert mosaic_input['upload']['filename'] == 'proposed.txt'
        assert mosaic_input['snapshot']['form_values']['mosaic_complete'] == 'on'
        assert mosaic_input['snapshot']['form_values']['mosaic_fixed_icrs'] == 'on'
        batch_input = saved_input(owner, 'input_for_batch', batch.location)
        assert batch_input['snapshot']['workflow'] == 'MULTI_SOURCE_SINGLE'
        assert batch_input['upload']['raw'] == source_bytes
        assert batch_input['upload']['format'] == source_format
        source_artifact = next((tmp_path / 'artifacts').glob('*/source-list.bin'))
        listing = owner.get('/reports').text
        assert single.location in listing and batch.location in listing
        for url in (single.location, mosaic.location, batch.location):
            assert f'action="{url}/reuse"' in listing
        visitor_listing = visitor.get('/reports').text
        assert single.location not in visitor_listing
        assert 'Reuse settings' not in visitor_listing
        for url in (single.location, single.location + '/download/report',
                    batch.location, manifest_url, batch_report, batch_report + '/visualization',
                    batch_report + '/queue?view=review'):
            assert visitor.get(url).status_code == 404
        assert saved_input(visitor, 'input_for_report', single.location) is None
        assert saved_input(visitor, 'input_for_report', mosaic.location) is None
        assert saved_input(visitor, 'input_for_batch', batch.location) is None

        with owner.session_transaction() as browser_session:
            reuse_csrf = browser_session['assessment_reuse_csrf']
        with visitor.session_transaction() as browser_session:
            visitor_csrf = browser_session['assessment_reuse_csrf']
        assert owner.get(single.location + '/reuse').status_code == 405
        assert owner.post(single.location + '/reuse').status_code == 403
        assert visitor.post(single.location + '/reuse', data={'csrf': reuse_csrf}).status_code == 403
        assert visitor.post(single.location + '/reuse', data={'csrf': visitor_csrf}).status_code == 404
        assert visitor.post(batch.location + '/reuse', data={'csrf': visitor_csrf}).status_code == 404

        def unexpected_assessment(*args, **kwargs):
            pytest.fail('Restoring a draft started an assessment')

        with monkeypatch.context() as no_execution:
            no_execution.setattr(BrowserAssessment, 'assess', unexpected_assessment)
            no_execution.setattr(BrowserAssessment, 'assess_mosaic', unexpected_assessment)
            no_execution.setattr(BrowserAssessment, 'assess_queue_custom', unexpected_assessment)
            no_execution.setattr(BrowserAssessment, 'pin_queue_for_submission', unexpected_assessment)
            for url, path, expected in (
                    (single.location, '/proposed', 'value="201.365"'),
                    (mosaic.location, '/proposed/mosaic', 'Restored OT pointings'),
                    (batch.location, '/proposed/batch', 'Restored source list')):
                receipt = owner.post(url + '/reuse', data={'csrf': reuse_csrf})
                assert receipt.status_code == 303
                assert receipt.location.startswith(path + '?draft=')
                assert visitor.get(receipt.location).status_code == 404
                draft = owner.get(receipt.location)
                assert draft.status_code == 200
                assert expected in draft.text
                assert 'Settings restored from a previous assessment' in draft.text
                assert f'href="{url}">View original assessment</a>' in draft.text
                if url == single.location:
                    single_draft_url = receipt.location
                if url == batch.location:
                    batch_draft_url, batch_draft = receipt.location, draft
                if url == mosaic.location:
                    mosaic_draft_url, mosaic_draft = receipt.location, draft
            assert owner.get(single_draft_url.replace('/proposed?', '/proposed/batch?')).status_code == 404
            assert owner.get(single_draft_url + '&draft=ambiguous').status_code == 404
        edited = form_data.copy()
        edited['ra'] = '201.366'
        edited_report = owner.post(single_draft_url, data=edited)
        assert edited_report.status_code == 303 and edited_report.location != single.location
        edited_input = saved_input(owner, 'input_for_report', edited_report.location)
        assert restore_input_snapshot(edited_input['snapshot']).values['ra'] == '201.366'
        assert owner.get(single.location + '/download/report').data == download
        assert 'value="201.365"' in owner.get(single_draft_url).text
        assert edited_input['snapshot']['form_contract'] == single_input['snapshot']['form_contract']

        mosaic_state = restore_input_snapshot(mosaic_input['snapshot'])
        mosaic_post = mosaic_state.values | dict(rows=mosaic_state.rows,
            mosaic_upload_token=hidden(mosaic_draft, 'mosaic_upload_token'))
        assert mosaic_post['mosaic_upload_token']
        assert hidden(mosaic_draft, 'mosaic_complete') == 'on'
        assert hidden(mosaic_draft, 'mosaic_fixed_icrs') == 'on'
        assert 'proposed array: 7m' in mosaic_draft.text
        assert '3 input rows' in mosaic_draft.text
        validated = owner.post('/proposed/mosaic', data=mosaic_post | {'action': 'validate'})
        assert validated.status_code == 200 and 'Restored OT pointings' in validated.text
        mosaic_rerun = owner.post('/proposed/mosaic', data=mosaic_post | {'action': 'assess'})
        assert mosaic_rerun.status_code == 303 and mosaic_rerun.location != mosaic.location
        original_request = owner.get(mosaic.location + '/download/request').json
        assert owner.get(mosaic_rerun.location + '/download/request').json == original_request
        assert saved_input(owner, 'input_for_report', mosaic_rerun.location)['upload']['raw'] == OT
        assert hidden(owner.get(mosaic_draft_url), 'mosaic_upload_token') == mosaic_post['mosaic_upload_token']
        replacement_ot = OT.replace(b'201.366', b'201.367')
        preview = owner.post('/proposed/mosaic', data=mosaic_post | {
            'action': 'preview-pointings', 'ot_pointings': (BytesIO(replacement_ot), 'replacement.txt')})
        assert preview.status_code == 200
        assert 'replacement.txt' in preview.text and 'Restored OT pointings' not in preview.text
        assert saved_input(owner, 'input_for_report', mosaic.location)['upload']['raw'] == OT

        batch_form = restore_input_snapshot(batch_input['snapshot'])
        batch_post = batch_form.values | dict(rows=batch_form.rows, angular='0.45',
            batch_csrf=hidden(batch_draft, 'batch_csrf'),
            submission_token=hidden(batch_draft, 'submission_token'),
            source_upload_token=hidden(batch_draft, 'source_upload_token'))
        assert batch_post['source_upload_token']
        for source in manifest['sources']:
            assert source['source']['name'] in batch_draft.text
        preflight = owner.post('/proposed/batch', data=batch_post | {'action': 'validate'})
        assert preflight.status_code == 200
        batch_post['submission_token'] = hidden(preflight, 'submission_token')
        rerun = owner.post('/proposed/batch', data=batch_post | {'action': 'assess'})
        assert rerun.status_code == 303 and rerun.location != batch.location
        rerun_manifest = owner.get(rerun.location + '/download/manifest').json
        assert rerun_manifest['shared_setup']['document']['request']['angular_resolution']['value'] == '0.45'
        assert [entry['source'] for entry in rerun_manifest['sources']] == [
            entry['source'] for entry in manifest['sources']]
        assert saved_input(owner, 'input_for_batch', rerun.location)['upload']['raw'] == source_bytes
        assert owner.get(manifest_url).json == manifest
        assert hidden(owner.get(batch_draft_url), 'source_upload_token') == batch_post['source_upload_token']

        replacement = b'name,ra,dec,redshift\nReplacement,10,0,0.01\n'
        new_preview, replaced = upload(owner, data=batch_post, raw=replacement, format='csv')
        assert 'Replacement' in new_preview.text and 'Restored source list' not in new_preview.text
        assert replaced['source_upload_token'] != batch_post['source_upload_token']
        assert saved_input(owner, 'input_for_batch', batch.location)['upload']['raw'] == source_bytes
        drafts = app.extensions['assessment_drafts']
        expired = drafts.clock() + drafts.ttl + 1
        monkeypatch.setattr(drafts, 'clock', lambda: expired)
        assert owner.get(single_draft_url).status_code == 404

        source_artifact.write_bytes(source_bytes[:-1] + b' ')
        with pytest.raises(ValueError, match='digest mismatch'):
            saved_input(owner, 'input_for_batch', batch.location)
        assert owner.post(batch.location + '/reuse', data={'csrf': reuse_csrf}).status_code == 409
        assert owner.get(manifest_url).json == manifest
        with engine.begin() as connection:
            connection.execute(assessment_input_links.delete().where(
                assessment_input_links.c.report_id == single.location.rsplit('/', 1)[-1]))
        legacy_listing = owner.get('/reports').text
        assert 'Saved settings unavailable' in legacy_listing
        assert f'href="{single.location}"' in legacy_listing
        assert f'action="{single.location}/reuse"' not in legacy_listing
        assert owner.get(single.location).status_code == 200
        visitor_report = visitor.post('/proposed', data=form_data)
        assert visitor_report.status_code == 303
        assert visitor_report.location in visitor.get('/reports').text
        assert owner.get(visitor_report.location).status_code == 404
    finally:
        close(app)
        engine.dispose()
