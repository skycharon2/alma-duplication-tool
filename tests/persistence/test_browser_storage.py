"""Anonymous browser report access survives a restart and stays private."""
import os
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from alma_duplicate.ui import create_app
from tests.persistence.test_foundation import config as migration_config
from tests.ui.test_batch_routes import upload
from tests.ui.test_queue_custom_mosaic import form
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


def test_reports_and_completed_batches_survive_browser_app_restart(tmp_path, database):
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
        _, data = upload(owner)
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
        listing = owner.get('/reports').text
        assert single.location in listing and batch.location in listing
        assert single.location not in visitor.get('/reports').text
        for url in (single.location, single.location + '/download/report',
                    batch.location, manifest_url, batch_report, batch_report + '/visualization',
                    batch_report + '/queue?view=review'):
            assert visitor.get(url).status_code == 404
        visitor_report = visitor.post('/proposed', data=form_data)
        assert visitor_report.status_code == 303
        assert visitor_report.location in visitor.get('/reports').text
        assert owner.get(visitor_report.location).status_code == 404
    finally:
        close(app)
        engine.dispose()
