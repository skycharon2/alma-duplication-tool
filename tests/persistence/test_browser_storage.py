"""Anonymous browser report access survives a restart and stays private."""
import os
from uuid import uuid4

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from alma_duplicate.ui import create_app
from alma_duplicate.ui.input_snapshot import restore_input_snapshot
from tests.persistence.test_foundation import config as migration_config
from tests.ui.test_batch_routes import upload
from tests.ui.test_batch_assessment import RAW
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
    ('csv', RAW),
    ('txt', b'name ra dec redshift\r\nfirst 201.365 -43.019 0.024\r\nsecond 201.365 -43.019 0\r\n'),
])
def test_reports_and_completed_batches_survive_browser_app_restart(tmp_path, database,
                                                                    source_format, source_bytes):
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
        for key in ('assessment_runs', 'source_uploads', 'mosaic_uploads'):
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
        form_data = form()
        form_data['geometry'] = 'SINGLE_POINTING'
        form_data.update(dict(ra='201.365', dec='-43.019', action='assess'))
        assert owner.post('/proposed', data=form_data,
                          headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        single = owner.post('/proposed', data=form_data)
        assert single.status_code == 303, single.text
        mosaic = submit(owner, form())
        assert mosaic.status_code == 303, mosaic.text
        _, data = upload(owner, raw=source_bytes, format=source_format)
        batch = owner.post('/proposed/batch', data=data | {'action': 'assess'})
        assert batch.status_code == 303, batch.text
        manifest_url = batch.location + '/download/manifest'
        manifest = owner.get(manifest_url).json
        batch_runs = [r['run_id'] for s in manifest['sources'] for r in s['reports']]
        assert len(batch_runs) == 4 and all(batch_runs)
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
        batch_input = saved_input(owner, 'input_for_batch', batch.location)
        assert batch_input['snapshot']['workflow'] == 'MULTI_SOURCE_SINGLE'
        assert batch_input['upload']['raw'] == source_bytes
        assert batch_input['upload']['format'] == source_format
        listing = owner.get('/reports').text
        assert single.location in listing and batch.location in listing
        assert single.location not in visitor.get('/reports').text
        for url in (single.location, single.location + '/download/report',
                    batch.location, manifest_url, batch_report, batch_report + '/visualization',
                    batch_report + '/queue?view=review'):
            assert visitor.get(url).status_code == 404
        assert saved_input(visitor, 'input_for_report', single.location) is None
        assert saved_input(visitor, 'input_for_report', mosaic.location) is None
        assert saved_input(visitor, 'input_for_batch', batch.location) is None
        path = next((tmp_path / 'artifacts').glob('*/source-list.bin'))
        path.write_bytes(source_bytes[:-1] + b' ')
        with pytest.raises(ValueError, match='digest mismatch'):
            saved_input(owner, 'input_for_batch', batch.location)
        assert owner.get(manifest_url).json == manifest
        visitor_report = visitor.post('/proposed', data=form_data)
        assert visitor_report.status_code == 303
        assert visitor_report.location in visitor.get('/reports').text
        assert owner.get(visitor_report.location).status_code == 404
    finally:
        close(app)
        engine.dispose()
