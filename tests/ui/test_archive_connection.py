"""The proposal form controls both live Archive clients per assessment."""
from dataclasses import replace

import pytest
import requests

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.clients import archive_client, archive_aq_client
from alma_duplicate.clients.archive_client import ArchiveClient, TapExecutionError
from alma_duplicate.clients.archive_contract import ArchiveQueryErrorKind
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
from alma_duplicate.ui import create_app
from tests.fakes import FakeTapExecutor
from tests.integration.test_live_aq_assessment import tap_rows
from tests.ui.test_live_source import live_config, line_form
from tests.unit.test_archive_aq_client import Http, Reply, hit, response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **kw: pytest.fail('Unexpected network request'))


@pytest.mark.parametrize('choice,origins', [
    ('AUTO', ARCHIVE_ORIGINS),
    *[(choice, (origin,)) for choice, origin in zip(
        ('EUROPE', 'EAST_ASIA', 'NORTH_AMERICA'), ARCHIVE_ORIGINS)],
])
@pytest.mark.parametrize('failure', [None, 'TAP', 'AQ'])
def test_selected_connection_reaches_both_clients_and_bounds_failover(monkeypatch, choice, origins, failure):
    source, _ = tap_rows()
    tap_calls, aq_calls = [], []

    class Tap:
        def __init__(self, endpoint, **kwargs):
            self.endpoint = endpoint
            tap_calls.append(endpoint)

        def search(self, spec):
            if failure == 'TAP':
                return ArchiveClient(self.endpoint, executor=FakeTapExecutor([
                    TapExecutionError(ArchiveQueryErrorKind.SERVICE_ERROR, 'Unavailable')])).search(spec)
            return replace(source, provenance=replace(source.provenance, endpoint=self.endpoint))

    def aq_factory(*, origin):
        aq_calls.append(origin)
        http = Http(requests.Timeout()) if failure == 'AQ' else Http(
            Reply({'elasticsearchUrl': origin + '/aq/service/api/search'}),
            *[Reply(response([hit(member, name) for name in ('SourceA', 'SourceB')]))
              for member in dict.fromkeys(row['member_ous_uid'] for row in source.rows)])
        return ArchiveAqClient(origin=origin, request=http)

    monkeypatch.setattr(archive_client, 'ArchiveClient', Tap)
    monkeypatch.setattr(archive_aq_client, 'ArchiveAqClient', aq_factory)
    client = create_app(live_config(LIVE_AQ=True)).test_client()
    form = line_form()
    form['archive_connection'] = choice
    result = client.post('/proposed', data=form)
    assert result.status_code == 303
    assert tap_calls == [origin + '/tap' for origin in (origins if failure == 'TAP' else origins[:1])]
    assert aq_calls == ([] if failure == 'TAP' else list(origins if failure == 'AQ' else origins[:1]))
    html = client.get(result.location).text
    assert ('Needs attention' if failure else 'Retrieval completed') in html


def test_selection_survives_edits_and_rejects_arbitrary_endpoints():
    client = create_app(live_config()).test_client()
    form = line_form('add')
    form['archive_connection'] = 'EAST_ASIA'
    html = client.post('/proposed', data=form).text
    assert '<option value="EAST_ASIA" selected>' in html
    form['archive_connection'] = 'https://example.org'
    assert client.post('/proposed', data=form).status_code == 400
    form.setlist('archive_connection', ['EUROPE', 'NORTH_AMERICA'])
    assert client.post('/proposed', data=form).status_code == 400


def test_offline_form_does_not_offer_live_selection():
    client = create_app(live_config(LIVE_ARCHIVE=False)).test_client()
    assert 'name="archive_connection"' not in client.get('/proposed').text
