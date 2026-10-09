"""Real execution counters are isolated from science and between browser requests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from alma_duplicate.progress import emit_progress, observe_progress
from alma_duplicate.ui import create_app
from alma_duplicate.ui.progress import ProgressStore
from alma_duplicate.ui.runs import BrowserAssessment
from tests.ui.test_runs import config, line_form

TOKEN = 'a' * 32


def test_store_capacity_expiry_and_snapshots():
    now = [0]
    store = ProgressStore(limit=2, max_active=2, ttl=10, clock=lambda: now[0])
    assert store.begin('one') and store.begin('two')
    assert not store.begin('one') and not store.begin('three')
    store.update('one', dict(stage='evaluation', completed=1, total=2, unit='candidates'))
    snapshot = store.get('one')
    snapshot['stages']['evaluation']['completed'] = 99
    assert store.get('one')['stages']['evaluation']['completed'] == 1
    now[0] = 11
    assert store.get('one')['status'] == 'RUNNING'  # Do not silently evict active work.
    store.finish('one', report_url='/runs/one')
    assert store.begin('three')  # Only the completed record may be evicted.
    assert store.get('one') is None
    store.finish('two')
    now[0] = 22
    assert store.get('two') is None
    assert store.get('three')['status'] == 'RUNNING'


def test_real_progress_counts_all_contexts_and_keeps_exports(monkeypatch):
    app = create_app(config(LIVE_AQ=False))
    store = app.extensions['assessment_progress']
    events = []
    update = store.update

    def capture(token, event):
        events.append(event)
        update(token, event)

    monkeypatch.setattr(store, 'update', capture)
    data = line_form()
    data.setlist('sources', ['ARCHIVE', 'QUEUE'])
    client = app.test_client()
    response = client.post('/proposed', data=data, headers={'X-Assessment-Progress': TOKEN})
    assert response.status_code == 200
    report_url = response.get_json()['report_url']
    report = client.get(report_url + '/download/report').get_json()
    evaluations = [e for e in events if e['stage'] == 'evaluation']
    n = len(report['context_evaluations'])
    assert n > 1  # The form display cap is one; progress covers every retained context.
    assert [e['completed'] for e in evaluations] == list(range(n + 1))
    assert {e['total'] for e in evaluations} == {n}
    ready = [e for e in events if e['stage'].endswith('_ready')]
    assert sum(e['completed'] for e in ready) == n
    assert events.index(evaluations[0]) > events.index(ready[-1])
    assert events[-1]['stage'] == 'storage' and events[-1]['completed'] > 0
    state = client.get('/assessment-progress/' + TOKEN)
    assert state.json['status'] == 'COMPLETED' and state.json['report_url'] == report_url
    assert state.headers['Cache-Control'] == 'no-store'
    assert 'stages' not in report and report['report_version'] == '5'
    # Polls, page reads and downloads never restart the assessment.
    count = len(events)
    client.get(report_url)
    client.get(report_url + '/download/request')
    client.get('/assessment-progress/' + TOKEN)
    assert len(events) == count
    assert client.post('/proposed', data=data, headers={'X-Assessment-Progress': TOKEN}).status_code == 429
    app.extensions['assessment_runs'].close()


def test_progress_can_be_polled_while_post_runs_and_is_request_local(monkeypatch):
    app = create_app(config(LIVE_AQ=False))
    entered, release = Event(), Event()
    original = BrowserAssessment.assess

    def blocked(self, document):
        emit_progress('aq', 1, 3, 'members')
        entered.set()
        assert release.wait(10)
        return original(self, document)

    monkeypatch.setattr(BrowserAssessment, 'assess', blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        post = pool.submit(lambda: app.test_client().post('/proposed', data=line_form(),
                           headers={'X-Assessment-Progress': TOKEN}))
        try:
            assert entered.wait(10)
            client = app.test_client()
            state = client.get('/assessment-progress/' + TOKEN).json
            assert state['status'] == 'RUNNING' and state['stages']['aq']['completed'] == 1
            assert client.get('/assessment-progress/' + 'b' * 32).status_code == 404
            emit_progress('evaluation', 99, 99, 'candidates')  # This thread has no observer.
            assert client.get('/assessment-progress/' + TOKEN).json == state
        finally:
            release.set()
        assert post.result(timeout=10).status_code == 200
    app.extensions['assessment_runs'].close()


def test_failures_and_invalid_input_do_not_publish_completed_report(monkeypatch):
    app = create_app(config(LIVE_AQ=False))
    client = app.test_client()
    invalid = line_form()
    invalid['ra'] = 'invalid'
    assert client.post('/proposed', data=invalid, headers={'X-Assessment-Progress': TOKEN}).status_code == 200
    assert client.get('/assessment-progress/' + TOKEN).status_code == 404
    assert client.post('/proposed', data=line_form(), headers={'X-Assessment-Progress': 'invalid'}).status_code == 400

    def fail(*args):
        emit_progress('report')
        raise ValueError('source failure')

    monkeypatch.setattr(BrowserAssessment, 'assess', fail)
    response = client.post('/proposed', data=line_form(), headers={'X-Assessment-Progress': TOKEN})
    assert b'Assessment could not be completed' in response.data
    state = client.get('/assessment-progress/' + TOKEN).json
    assert state['status'] == 'FAILED' and 'report_url' not in state
    app.extensions['assessment_runs'].close()


def test_observer_failure_and_nested_scopes_do_not_leak():
    outer, inner = [], []
    with observe_progress(outer.append):
        emit_progress('archive_search')
        with observe_progress(inner.append):
            emit_progress('queue_load')
        emit_progress('report')
    emit_progress('storage')
    assert [e['stage'] for e in outer] == ['archive_search', 'report']
    assert [e['stage'] for e in inner] == ['queue_load']
    with observe_progress(lambda e: (_ for _ in ()).throw(ValueError('broken observer'))):
        emit_progress('evaluation', 1, 1, 'candidates')
