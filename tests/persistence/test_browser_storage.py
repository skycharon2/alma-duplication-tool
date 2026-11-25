"""Anonymous browser report access survives a restart and stays private."""
import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from alembic import command
from sqlalchemy import create_engine, select
from sqlalchemy.schema import CreateSchema, DropSchema
from werkzeug.datastructures import MultiDict

from alma_duplicate.persistence.models import (
    assessment_input_links, assessment_input_snapshots, browser_artifact_cleanup,
    browser_assessment_trash, browser_batches, browser_reports,
)
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
    ('csv', ('name,ra,dec,redshift\n' + ''.join(
        f'target-{i},201.365,-43.019,0\n' for i in range(10))).encode()),
    ('txt', b'name ra dec redshift\r\nfirst 201.365 -43.019 0.024\r\nsecond 201.365 -43.019 0\r\n'),
])
def test_reports_and_completed_batches_survive_browser_app_restart(tmp_path, database,
                                                                    source_format, source_bytes, monkeypatch):
    from alma_duplicate.artifacts import local
    monkeypatch.setattr(local, '_COMPRESSION_MIN_SIZE', 1)
    url, options = database
    retention_days = 7 if source_format == 'csv' else 3
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
            'REPORT_TRASH_RETENTION_DAYS': retention_days,
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
        mosaic_form.setlist('sources', ['ARCHIVE', 'QUEUE'])
        mosaic_form['mosaic_array'] = '7m'
        mosaic_form['mosaic_complete'] = 'on'
        mosaic_form['mosaic_fixed_icrs'] = 'on'
        mosaic = submit(owner, mosaic_form)
        assert mosaic.status_code == 303, mosaic.text
        _, data = upload(owner, raw=source_bytes, format=source_format)
        batch = owner.post('/proposed/batch', data=data | {'action': 'assess', 'batch_name': 'Original survey'})
        assert batch.status_code == 303, batch.text
        manifest_url = batch.location + '/download/manifest'
        manifest = owner.get(manifest_url).json
        assert manifest['name'] == 'Original survey'
        batch_runs = [r['run_id'] for s in manifest['sources'] for r in s['reports']]
        assert len(batch_runs) == 2 * len(manifest['sources']) and all(batch_runs)
        batch_report = '/runs/' + batch_runs[0]
        download = owner.get(single.location + '/download/report').data
        assert list((tmp_path / 'artifacts').glob('*/report.json.gz'))
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
        with owner.session_transaction() as browser_session:
            browser_session.pop('report_history', None)
            browser_session.pop('batch_history', None)
            browser_session.pop('mosaic_report_groups', None)
            browser_session.pop('partial_assessments', None)
        assert 'Archive results unavailable or incomplete.' in owner.get(mosaic.location).text
        assert 'Continuum · ARCHIVE: assessment unavailable.' in owner.get(
            mosaic.location + '/mosaic-visualization').text
        listing = owner.get('/reports').text
        assert 'href="/reports/storage"' in listing
        storage_page = owner.get('/reports/storage')
        assert storage_page.status_code == 200
        assert 'Browser storage quota</dt><dd>None' in storage_page.text
        assert f'<dd>{retention_days} days</dd>' in storage_page.text
        owner_usage = [int(value) for value in re.findall(r'<data value="(\d+)">', storage_page.text)]
        assert owner_usage[0] == owner_usage[1] > 0 and owner_usage[2] == 0
        row_sizes = [int(value) for value in re.findall(r'<data value="(\d+)">', listing)]
        assert len(row_sizes) == 3 and sum(row_sizes) == owner_usage[0]
        assert re.findall(r'<data value="(\d+)">', visitor.get('/reports/storage').text) == ['0'] * 3
        assert single.location in listing and batch.location in listing
        assert f'href="{batch_report}"' not in listing
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
        assert owner.post(single.location + '/reuse', data=MultiDict([
            ('csrf', reuse_csrf), ('csrf', reuse_csrf),
        ])).status_code == 403
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
                wrong_path = '/proposed/mosaic' if path == '/proposed' else '/proposed'
                assert owner.get(wrong_path + '?' + receipt.location.split('?', 1)[1]).status_code == 404
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
        assert 'Original survey' not in batch_draft.text
        batch_post = batch_form.values | dict(rows=batch_form.rows, angular='0.45', batch_name='Survey at 0.45 arcsec',
            batch_csrf=hidden(batch_draft, 'batch_csrf'),
            submission_token=hidden(batch_draft, 'submission_token'),
            source_upload_token=hidden(batch_draft, 'source_upload_token'))
        assert batch_post['source_upload_token']
        for source in manifest['sources']:
            assert source['source']['name'] in batch_draft.text
        preflight = owner.post('/proposed/batch', data=batch_post | {'action': 'validate'})
        assert preflight.status_code == 200
        assert 'value="Survey at 0.45 arcsec"' in preflight.text
        batch_post['submission_token'] = hidden(preflight, 'submission_token')
        rerun = owner.post('/proposed/batch', data=batch_post | {'action': 'assess'})
        assert rerun.status_code == 303 and rerun.location != batch.location
        rerun_manifest = owner.get(rerun.location + '/download/manifest').json
        assert rerun_manifest['name'] == 'Survey at 0.45 arcsec'
        history = owner.get('/reports').text
        assert 'Original survey' in history and 'Survey at 0.45 arcsec' in history
        assert '0.45 arcsec resolution' in history
        rename_url = f'/reports/manage/batch/{batch.location.rsplit("/", 1)[-1]}/rename'
        assert f'href="{rename_url}"' in history
        rename_page = owner.get(rename_url)
        assert rename_page.status_code == 200
        assert visitor.get(rename_url).status_code == 404
        with owner.session_transaction() as browser_session:
            rename_csrf = browser_session['report_management_csrf']
        with visitor.session_transaction() as browser_session:
            foreign_csrf = browser_session['report_management_csrf']
        assert visitor.post(rename_url, data={
            'csrf': foreign_csrf, 'display_name': 'Foreign name',
        }).status_code == 404
        assert owner.post(rename_url, data={'display_name': 'Missing CSRF'}).status_code == 403
        assert owner.post(rename_url, data={
            'csrf': rename_csrf, 'display_name': 'x' * 81,
        }).status_code == 400
        assert owner.post(rename_url, data={
            'csrf': rename_csrf, 'display_name': 'Saved baseline',
        }).status_code == 303
        assert 'Saved baseline' in owner.get('/reports').text
        search_page = owner.get('/reports?q=sAvEd+baseline').text
        assert f'href="{batch.location}"' in search_page
        assert f'href="{rerun.location}"' not in search_page
        assert 'No matching reports' in visitor.get('/reports?q=Saved+baseline').text
        assert 'No matching reports' in owner.get('/reports?q=%25').text
        batches_only = owner.get('/reports?kind=batch').text
        assert f'href="{batch.location}"' in batches_only and '/runs/' not in batches_only
        standalone_only = owner.get('/reports?kind=report').text
        assert f'href="{single.location}"' in standalone_only and '/batches/' not in standalone_only
        assert 'No matching reports' in owner.get('/reports?q=Saved+baseline&kind=report').text
        assert owner.get('/reports?kind=invalid').status_code == 400
        assert owner.get(manifest_url).json == manifest
        assert owner.post(rename_url, data={'csrf': rename_csrf, 'display_name': ''}).status_code == 303
        history = owner.get('/reports').text
        assert 'Saved baseline' not in history and 'Original survey' in history
        single_rename = f'/reports/manage/report/{single.location.rsplit("/", 1)[-1]}/rename'
        assert owner.post(single_rename, data={
            'csrf': rename_csrf, 'display_name': 'Single pointing baseline',
        }).status_code == 303
        assert 'Single pointing baseline' in owner.get('/reports').text
        assert owner.get(single.location + '/download/report').data == download
        batch_entry = f'batch:{batch.location.rsplit("/", 1)[-1]}'
        report_entry = f'report:{single.location.rsplit("/", 1)[-1]}'
        bulk_url = '/reports/manage/trash-selected'
        assert f'action="{bulk_url}"' in owner.get('/reports').text
        assert owner.post(bulk_url, data={'csrf': rename_csrf}).status_code == 400
        assert owner.post(bulk_url, data={
            'csrf': rename_csrf, 'entry': [batch_entry, f'batch:{"f" * 32}'],
        }).status_code == 404
        assert owner.get(batch.location).status_code == 200
        assert visitor.post(bulk_url, data={
            'csrf': foreign_csrf, 'entry': [batch_entry, report_entry],
        }).status_code == 404
        bulk_form = {'csrf': rename_csrf, 'entry': [batch_entry, report_entry, report_entry]}
        before_bulk_bytes = re.search(r'<data value="(\d+)">', owner.get('/reports/storage').text).group(1)
        assert owner.post(bulk_url, data=bulk_form).status_code == 303
        assert owner.post(bulk_url, data=bulk_form).status_code == 303
        assert owner.get(batch.location).status_code == 404
        assert owner.get(batch_report).status_code == 404
        assert owner.get(single.location).status_code == 404
        after_bulk = [int(value) for value in re.findall(
            r'<data value="(\d+)">', owner.get('/reports/storage').text)]
        assert after_bulk[0] == int(before_bulk_bytes) == after_bulk[1] + after_bulk[2]
        assert after_bulk[1] > 0 and after_bulk[2] > 0
        bulk_trash_page = owner.get('/reports/trash').text
        assert bulk_trash_page.count('>Restore</button>') == 2
        trash_sizes = [int(value) for value in re.findall(r'<data value="(\d+)">', bulk_trash_page)]
        assert len(trash_sizes) == 2 and sum(trash_sizes) == after_bulk[2]
        for entry in (batch_entry, report_entry):
            assert owner.post(f'/reports/manage/{entry.replace(":", "/", 1)}/restore',
                              data={'csrf': rename_csrf}).status_code == 303
        assert owner.get(manifest_url).json == manifest
        assert owner.get(single.location + '/download/report').data == download
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
        with engine.begin() as connection:
            original = connection.execute(select(browser_reports).where(
                browser_reports.c.id == single.location.rsplit('/', 1)[-1])).mappings().one()
            timestamp = datetime.now(timezone.utc) + timedelta(seconds=1)
            for index in range(21):
                run_id = f'{index:032x}.{index:032x}'
                overview = original['overview'] | {
                    'listing': original['overview']['listing'] | {'id': run_id},
                }
                connection.execute(browser_reports.insert().values(
                    dict(original) | dict(id=run_id, overview=overview,
                        created_at=timestamp)))
            connection.execute(browser_batches.insert(), [
                dict(id=f'{index:032x}', owner_digest=original['owner_digest'],
                     created_at=timestamp, manifest=manifest | {'batch_id': f'{index:032x}'})
                for index in range(41)
            ])
        first_page = owner.get('/reports')
        filtered_first = owner.get('/reports?q=Original+survey&kind=batch')
        filtered_url = re.search(r'href="([^"]+)">Older reports</a>', filtered_first.text).group(1)
        filtered_url = filtered_url.replace('&amp;', '&')
        assert 'q=Original+survey' in filtered_url
        assert 'kind=batch' in filtered_url
        assert owner.get(filtered_url).status_code == 200
        assert owner.get(filtered_url.replace('Original+survey', 'different')).status_code == 400
        assert owner.get(filtered_url.replace('kind=batch', 'kind=report')).status_code == 400
        assert 'Older reports' in first_page.text and single.location not in first_page.text
        older_url = re.search(r'href="([^"]+)">Older reports</a>', first_page.text).group(1)
        with engine.begin() as connection:
            newest_id = 'a' * 32 + '.' + 'b' * 32
            connection.execute(browser_reports.insert().values(
                dict(original) | dict(id=newest_id, overview=original['overview'] | {
                    'listing': original['overview']['listing'] | {'id': newest_id},
                }, created_at=timestamp + timedelta(seconds=1))))
        second_page = owner.get(older_url)
        assert 'Newest reports' in second_page.text and single.location in second_page.text
        third_url = re.search(r'href="([^"]+)">Older reports</a>', second_page.text).group(1)
        third_page = owner.get(third_url)
        assert third_page.status_code == 200
        assert f'href="{batch.location}"' in third_page.text
        assert '/runs/' not in third_page.text
        assert 'Older reports' not in third_page.text
        for index in range(41):
            link = f'href="/batches/{index:032x}"'
            assert sum(link in page.text for page in (first_page, second_page, third_page)) == 1
        assert f'href="/runs/{newest_id}"' in owner.get('/reports').text
        for index in range(21):
            link = f'href="/runs/{index:032x}.{index:032x}"'
            assert (link in first_page.text) != (link in second_page.text)
        assert visitor.get(older_url).status_code == 400
        assert owner.get(older_url + 'tampered').status_code == 400
        assert owner.get('/reports?older=invalid').status_code == 400
        with engine.begin() as connection:
            connection.execute(browser_reports.delete().where(
                browser_reports.c.id == f'{1:032x}.{1:032x}'))
            connection.execute(browser_batches.delete().where(
                browser_batches.c.id == f'{21:032x}'))
        assert owner.get(older_url).text == second_page.text
        batch_id = batch.location.rsplit('/', 1)[-1]
        trash_url = f'/reports/manage/batch/{batch_id}/trash'
        restore_url = f'/reports/manage/batch/{batch_id}/restore'
        assert 'href="/reports/trash"' in first_page.text
        assert 'Trash is empty' in owner.get('/reports/trash').text
        with owner.session_transaction() as browser_session:
            csrf = browser_session['report_management_csrf']
        with visitor.session_transaction() as browser_session:
            visitor_csrf = browser_session['report_management_csrf']
        assert owner.get(trash_url).status_code == 405
        assert owner.post(trash_url).status_code == 403
        assert owner.post(trash_url, data={'csrf': csrf},
                          headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert owner.post(trash_url, data=MultiDict([('csrf', csrf), ('csrf', csrf)])).status_code == 403
        assert visitor.post(trash_url, data={'csrf': csrf}).status_code == 403
        assert visitor.post(trash_url, data={'csrf': visitor_csrf}).status_code == 404
        assert owner.post(f'/reports/manage/report/{batch_runs[0]}/trash',
                          data={'csrf': csrf}).status_code == 404
        assert owner.post(trash_url, data={'csrf': csrf}).status_code == 303
        assert 'Assessment moved to trash.' in owner.get('/reports').text
        trash_page = owner.get('/reports/trash')
        assert f'action="{restore_url}"' in trash_page.text
        assert f'value="{csrf}"' in trash_page.text
        assert restore_url not in visitor.get('/reports/trash').text
        with engine.connect() as db:
            trash_record = db.execute(select(browser_assessment_trash)).one()
        assert trash_record.purge_after - trash_record.deleted_at == timedelta(days=retention_days)
        deadline = trash_record.purge_after
        deadline = deadline.astimezone(timezone.utc) if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        assert 'Eligible for cleanup from' in trash_page.text
        assert f'datetime="{deadline.isoformat()}"' in trash_page.text
        assert owner.post(trash_url, data={'csrf': csrf}).status_code == 303
        with engine.connect() as db:
            assert db.execute(select(browser_assessment_trash)).one() == trash_record
        assert visitor.post(restore_url, data={'csrf': visitor_csrf}).status_code == 404
        for url in (batch.location, manifest_url, batch_report, batch_report + '/download/report'):
            assert owner.get(url).status_code == 404
        assert saved_input(owner, 'input_for_batch', batch.location) is None
        assert owner.get(rerun.location).status_code == 200
        assert saved_input(owner, 'input_for_batch', rerun.location)['upload']['raw'] == source_bytes
        assert owner.post(restore_url, data={'csrf': csrf}).status_code == 303
        assert owner.post(restore_url, data={'csrf': csrf}).status_code == 303
        restored_page = owner.get('/reports/trash').text
        assert 'Assessment restored to Existing reports.' in restored_page
        assert 'Trash is empty' in restored_page
        assert owner.get(manifest_url).json == manifest

        mosaic_id = mosaic.location.rsplit('/', 1)[-1]
        sibling_id = f'{uuid4().hex}.{uuid4().hex}'
        before_sibling = owner.get('/reports/storage').text
        with engine.begin() as db:
            branch = db.execute(select(browser_reports).where(
                browser_reports.c.id == mosaic_id)).mappings().one()
            db.execute(browser_reports.insert().values(dict(branch) | {'id': sibling_id}))
        assert owner.get('/reports/storage').text == before_sibling
        assert owner.get(f'/runs/{sibling_id}/download/report').status_code == 200
        assert owner.post(f'/reports/manage/report/{mosaic_id}/trash',
                          data={'csrf': csrf}).status_code == 303
        assert owner.get(mosaic.location).status_code == 404
        assert owner.get(f'/runs/{sibling_id}/download/report').status_code == 404
        assert owner.get('/reports/trash').text.count('>Restore</button>') == 1
        assert owner.post(f'/reports/manage/report/{sibling_id}/restore',
                          data={'csrf': csrf}).status_code == 303
        assert owner.get(mosaic.location).status_code == 200

        purge_url = f'/reports/manage/batch/{batch_id}/purge'
        confirmation = {'csrf': csrf, 'confirm': 'yes'}
        assert owner.get(purge_url).status_code == 404
        assert owner.post(purge_url, data=confirmation).status_code == 409
        assert owner.post(trash_url, data={'csrf': csrf}).status_code == 303
        assert f'href="{purge_url}"' in owner.get('/reports/trash').text
        confirm_page = owner.get(purge_url)
        assert confirm_page.status_code == 200
        assert 'Delete assessment permanently?' in confirm_page.text
        assert f'action="{purge_url}"' in confirm_page.text
        assert 'href="/reports/trash">Cancel</a>' in confirm_page.text
        assert 'name="confirm" value="yes"' in confirm_page.text
        assert f'action="{restore_url}"' in owner.get('/reports/trash').text
        assert visitor.get(purge_url).status_code == 404
        assert visitor.post(purge_url, data=confirmation | {'csrf': visitor_csrf}).status_code == 404
        assert owner.post(purge_url, data={'csrf': csrf}).status_code == 400
        assert owner.post(purge_url).status_code == 403

        from alma_duplicate.ui import report_management
        purge = report_management.purge_assessment

        def fail_after_queue(*args):
            purge(*args)
            raise RuntimeError('simulated commit failure')

        with monkeypatch.context() as rollback:
            rollback.setattr(report_management, 'purge_assessment', fail_after_queue)
            with pytest.raises(RuntimeError, match='simulated commit failure'):
                owner.post(purge_url, data=confirmation)
        with engine.connect() as db:
            assert db.execute(select(browser_artifact_cleanup)).first() is None
        assert f'action="{restore_url}"' in owner.get('/reports/trash').text

        assert owner.post(purge_url, data=confirmation).status_code == 303
        assert 'Assessment permanently deleted. File cleanup is queued.' in owner.get('/reports/trash').text
        assert owner.post(restore_url, data={'csrf': csrf}).status_code == 404
        assert owner.get(manifest_url).status_code == 404
        with engine.connect() as db:
            assert db.scalar(select(browser_batches.c.id).where(browser_batches.c.id == batch_id)) is None
            assert db.scalar(select(browser_reports.c.id).where(browser_reports.c.id.in_(batch_runs))) is None
            assert db.scalar(select(assessment_input_snapshots.c.id).where(
                assessment_input_snapshots.c.id == batch_input['snapshot_id'])) is None
            queued = db.scalars(select(browser_artifact_cleanup.c.storage_key)).all()
        assert queued and all((tmp_path / 'artifacts' / key).is_file() for key in queued)
        result = app.test_cli_runner().invoke(args=['cleanup-browser-artifacts', '--limit', '500'])
        assert result.exit_code == 0, result.output
        assert all(not (tmp_path / 'artifacts' / key).exists() for key in queued)
        assert owner.get(rerun.location).status_code == 200
        assert saved_input(owner, 'input_for_batch', rerun.location)['upload']['raw'] == source_bytes

        assert owner.post(f'/reports/manage/report/{mosaic_id}/trash',
                          data={'csrf': csrf}).status_code == 303
        assert owner.post(f'/reports/manage/report/{sibling_id}/purge',
                          data=confirmation).status_code == 303
        with engine.connect() as db:
            assert db.scalar(select(browser_reports.c.id).where(
                browser_reports.c.id.in_([mosaic_id, sibling_id]))) is None
        assert owner.get(mosaic_rerun.location).status_code == 200

        # The batch was created by this app process. Its in-memory copy must
        # not become visible after scheduled expiry removes the database row.
        due_id = rerun.location.rsplit('/', 1)[-1]
        future_id = mosaic_rerun.location.rsplit('/', 1)[-1]
        assert owner.post(f'/reports/manage/batch/{due_id}/trash',
                          data={'csrf': csrf}).status_code == 303
        assert owner.post(f'/reports/manage/report/{future_id}/trash',
                          data={'csrf': csrf}).status_code == 303
        past = datetime.now(timezone.utc) - timedelta(days=1)
        with engine.begin() as db:
            db.execute(browser_assessment_trash.update().where(
                browser_assessment_trash.c.assessment_kind == 'BATCH',
                browser_assessment_trash.c.assessment_id == due_id,
            ).values(deleted_at=past - timedelta(days=7), purge_after=past))
        runner = app.test_cli_runner()
        command_args = ['purge-expired-browser-assessments', '--limit', '1']
        result = runner.invoke(args=command_args)
        assert result.exit_code == 0, result.output
        assert 'Expired trash entries removed: 1' in result.output
        assert owner.get(rerun.location).status_code == 404
        assert 'Expired trash entries removed: 0' in runner.invoke(args=command_args).output
        assert owner.post(f'/reports/manage/report/{future_id}/restore',
                          data={'csrf': csrf}).status_code == 303
        assert owner.get(mosaic_rerun.location).status_code == 200

        # Let a browser act after the maintenance command has selected an
        # expired entry, immediately before the command acquires the row lock.
        future_trash = f'/reports/manage/report/{future_id}/trash'
        future_restore = f'/reports/manage/report/{future_id}/restore'
        assert owner.post(future_trash, data={'csrf': csrf}).status_code == 303
        with engine.begin() as db:
            db.execute(browser_assessment_trash.update().where(
                browser_assessment_trash.c.assessment_kind == 'REPORT',
            ).values(deleted_at=past - timedelta(days=retention_days), purge_after=past))
            queued_before = set(db.scalars(select(browser_artifact_cleanup.c.storage_key)))

        lock_assessment = report_management._lock_assessment
        selected = []

        def restore_before_maintenance_lock(db, owner_digest, kind, entry_id, *, group=False):
            if group:
                selected.append(entry_id)
                assert owner.post(future_restore, data={'csrf': csrf}).status_code == 303
                if source_format == 'txt':
                    assert owner.post(future_trash, data={'csrf': csrf}).status_code == 303
            return lock_assessment(db, owner_digest, kind, entry_id, group=group)

        with monkeypatch.context() as interleaving:
            interleaving.setattr(report_management, '_lock_assessment', restore_before_maintenance_lock)
            result = runner.invoke(args=command_args)
        assert result.exit_code == 0, result.output
        assert selected == [future_id]
        assert 'Expired trash entries removed: 0' in result.output
        with engine.connect() as db:
            assert set(db.scalars(select(browser_artifact_cleanup.c.storage_key))) == queued_before
        if source_format == 'txt':
            assert owner.get(mosaic_rerun.location).status_code == 404
            assert f'action="{future_restore}"' in owner.get('/reports/trash').text
            assert owner.post(future_restore, data={'csrf': csrf}).status_code == 303
        assert owner.get(mosaic_rerun.location).status_code == 200

        empty_url = '/reports/trash/empty'
        assert owner.get(empty_url).status_code == 303
        assert owner.post(future_trash, data={'csrf': csrf}).status_code == 303
        first_confirmation = owner.get(empty_url)
        assert '1 assessment<' in first_confirmation.text
        single_id = single.location.rsplit('/', 1)[-1]
        assert owner.post(f'/reports/manage/report/{single_id}/trash',
                          data={'csrf': csrf}).status_code == 303
        assert owner.post(empty_url, data={
            'csrf': csrf, 'confirmation': hidden(first_confirmation, 'confirmation'),
        }).status_code == 409
        assert owner.get('/reports/trash').text.count('>Restore</button>') == 2
        visitor_id = visitor_report.location.rsplit('/', 1)[-1]
        assert visitor.post(f'/reports/manage/report/{visitor_id}/trash',
                            data={'csrf': visitor_csrf}).status_code == 303
        confirmation_page = owner.get(empty_url)
        assert '2 assessments<' in confirmation_page.text
        bulk_confirmation = hidden(confirmation_page, 'confirmation')
        assert visitor.post(empty_url, data={
            'csrf': visitor_csrf, 'confirmation': bulk_confirmation,
        }).status_code == 400
        assert owner.post(empty_url, data={'confirmation': bulk_confirmation}).status_code == 403
        assert owner.post(empty_url, data={
            'csrf': csrf, 'confirmation': bulk_confirmation,
        }).status_code == 303
        assert 'Trash is empty' in owner.get('/reports/trash').text
        assert visitor.get('/reports/trash').text.count('>Restore</button>') == 1
        assert owner.post(future_restore, data={'csrf': csrf}).status_code == 404
        assert owner.post(empty_url, data={
            'csrf': csrf, 'confirmation': bulk_confirmation,
        }).status_code == 409
    finally:
        close(app)
        engine.dispose()
