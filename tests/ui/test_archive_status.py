"""Mirror status is report evidence, never an implicit health probe."""
from dataclasses import replace

import pytest

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.ui import create_app
from alma_duplicate.ui.archive_status import archive_run_status
from tests.ui.test_live_source import live_config, line_form
from tests.ui import test_live_aq

# Register shared pytest fixtures explicitly, including the autouse network guard.
wired = test_live_aq.wired
no_network = test_live_aq.no_network


def test_form_shows_unchecked_policy_without_contacting_sources():
    client = create_app(live_config()).test_client()
    html = client.get('/proposed').text
    assert 'id="archive_connection"' in html
    assert 'Automatic — Europe → East Asia → North America' in html
    assert 'Selecting a region uses only that site' in html
    assert 'Connection starts when you run the assessment.' in html


@pytest.mark.parametrize('status,aq_status,label', [
    ('COMPLETED', 'COMPLETED', 'Retrieval completed'),
    ('FAILED', 'SKIPPED', 'Needs attention'),
    ('INCOMPLETE', 'SKIPPED', 'Needs attention'),
    ('COMPLETED', 'FAILED', 'Needs attention'),
])
def test_tap_and_aq_are_independent_and_failure_is_visible(status, aq_status, label):
    attempts = [{'origin': o, 'status': 'FAILED', 'finished_at': '2026-10-16T10:00:00Z'}
                for o in ARCHIVE_ORIGINS]
    source = {'status': status, 'source_metadata': {'provenance': {
        'endpoint': ARCHIVE_ORIGINS[1] + '/tap', 'mirror_attempts': attempts[:2]}},
        'array_evidence': {'acquisition': {'status': aq_status,
            'properties_url': ARCHIVE_ORIGINS[2] + '/aq/service/api/v1/properties',
            'mirror_attempts': attempts}}}
    view = archive_run_status({'sources': {'ARCHIVE': source}})
    assert view['label'] == label
    tap, aq = view['stages']
    assert (tap['region'], aq['region']) == ('East Asia', 'North America')
    assert tap['switched'] is (status == 'COMPLETED')
    assert aq['switched'] is (aq_status == 'COMPLETED')
    assert len(aq['attempts']) == 3


def test_old_reports_replay_and_absent_archive():
    assert archive_run_status({}) is None
    assert archive_run_status({'sources': {'ARCHIVE': {'status': 'NOT_SELECTED'}}}) is None
    replay = archive_run_status({'sources': {'ARCHIVE': {'status': 'COMPLETED', 'replay': {'fixture_kind': 'RECORDED'}}}})
    assert replay['label'] == 'Recorded data' and replay['tone'] == 'neutral'
    old = archive_run_status({'sources': {'ARCHIVE': {'status': 'COMPLETED'}}})
    assert old['stages'][0]['region'] == 'Not recorded'
    assert old['stages'][0]['attempts'] == []


def test_report_visible_without_technical_mode_and_read_only(wired):
    wired['source'] = replace(wired['source'], provenance=replace(wired['source'].provenance,
        endpoint=ARCHIVE_ORIGINS[1] + '/tap'))
    client = create_app(live_config(LIVE_AQ=True)).test_client()
    response = client.post('/proposed', data=line_form())
    assert response.status_code == 303
    events = list(wired['events'])
    html = client.get(response.location).text
    assert 'id="archive-source-status"' in html
    assert 'Candidate search (TAP)</strong>: Completed · East Asia' in html
    assert 'Array evidence (AQ)</strong>: Completed · Europe' in html
    assert 'Recorded for this assessment only' in html
    assert wired['events'] == events
