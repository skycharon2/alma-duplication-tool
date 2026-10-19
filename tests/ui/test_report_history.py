"""Recent browser reports remain discoverable without listing other users' runs."""
from tests.ui.test_live_source import line_form, live_config, ARCHIVE_REPLAY
from alma_duplicate.ui import create_app


def app_for(**settings):
    return create_app(live_config(LIVE_ARCHIVE=False,
                                 OFFLINE_ARCHIVE_REPLAY=str(ARCHIVE_REPLAY), **settings))


def test_history_survives_return_to_form_and_is_browser_scoped():
    app = app_for()
    client = app.test_client()
    other = app.test_client()
    first = client.post('/proposed', data=line_form())
    assert first.status_code == 303
    form = line_form()
    form['target_name'] = 'Second target <script>alert(1)</script>'
    second = client.post('/proposed', data=form)
    assert second.status_code == 303
    client.get('/proposed')
    html = client.get('/reports').text
    assert first.location in html and second.location in html
    assert html.index(second.location) < html.index(first.location)
    assert '&lt;script&gt;' in html
    assert '<script>alert(1)</script>' not in html
    assert first.location not in other.get('/reports').text
    assert client.get(first.location).status_code == 200
    assert 'Download important reports' in html


def test_evicted_runs_are_removed_and_reading_does_not_extend_expiry():
    app = app_for(MAX_RETAINED_RUNS=1, MAX_RUN_AGE_SECONDS=10)
    store = app.extensions['assessment_runs']
    now = [0]
    store._clock = lambda: now[0]
    client = app.test_client()
    first = client.post('/proposed', data=line_form())
    second = client.post('/proposed', data=line_form())
    html = client.get('/reports').text
    assert first.location not in html and second.location in html
    now[0] = 9
    assert second.location in client.get('/reports').text
    now[0] = 10
    assert second.location not in client.get('/reports').text
    assert client.get(second.location).status_code == 404


def test_validation_does_not_add_a_report():
    client = app_for().test_client()
    client.post('/proposed', data=line_form('validate'))
    assert 'No retained assessments for this browser' in client.get('/reports').text
