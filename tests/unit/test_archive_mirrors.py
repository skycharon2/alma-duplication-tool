"""Whole-operation failover, provenance and conservative failure boundaries."""
import hashlib
import json

import pytest
import requests

from alma_duplicate.archive_endpoints import (
    ARCHIVE_ORIGINS as ORIGINS, ArchiveBudgetExpired, request_budget, request_timeout,
)
from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient, MirroredArchiveAqClient
from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient, ArchiveAqError
from alma_duplicate.clients.archive_contract import ArchiveQueryErrorKind as K, ArchiveQueryStatus as S, TapExecutionError
from tests.fakes import FakeTapExecutor
from tests.unit.test_archive_client import _spec, _count_response, _retrieval_response
from tests.unit.test_archive_aq_client import MEMBER, OTHER, Http, Reply, hit, response


@pytest.mark.parametrize("failure", [
    TapExecutionError(K.SERVICE_ERROR, "offline"),
    TapExecutionError(K.RESPONSE_FORMAT_ERROR, "truncated"),
    "OVERFLOW", "COUNT_MISMATCH",
])
def test_tap_restarts_whole_query_and_keeps_only_successful_rows(failure):
    first = ([_count_response(3), _retrieval_response(1, status="OVERFLOW")]
             if failure == "OVERFLOW" else [_count_response(3), _retrieval_response(1)]
             if failure == "COUNT_MISMATCH" else [failure])
    executors = [FakeTapExecutor(first), FakeTapExecutor([_count_response(2), _retrieval_response(2)])]
    calls = []
    def factory(endpoint, **kwargs):
        calls.append(endpoint)
        return ArchiveClient(endpoint, executor=executors[len(calls)-1], **kwargs)
    result = MirroredArchiveClient(client_factory=factory).search(_spec())
    assert result.status is S.COMPLETE and len(result.rows) == 2
    assert calls == [o + "/tap" for o in ORIGINS[:2]]
    assert result.provenance.endpoint == ORIGINS[1] + "/tap"
    assert len(result.provenance.mirror_attempts) == 2
    assert [c.adql for c in executors[1].calls][0].startswith("SELECT COUNT")
    assert len(executors[1].projection_calls) == 1
    assert result.provenance.mirror_attempts[-1]["query_hash"] == result.provenance.query_hash


@pytest.mark.parametrize("kind", [K.QUERY_ERROR, K.SCHEMA_DRIFT])
def test_tap_contract_errors_do_not_switch(kind):
    calls = []
    def factory(endpoint, **kwargs):
        calls.append(endpoint)
        return ArchiveClient(endpoint, executor=FakeTapExecutor([TapExecutionError(kind, "bad query")]), **kwargs)
    result = MirroredArchiveClient(client_factory=factory).search(_spec())
    assert result.error_kind is kind and len(calls) == 1


def test_tap_complete_empty_stops_and_all_failures_remain_errors():
    for empty in [True, False]:
        calls = []
        def factory(endpoint, **kwargs):
            calls.append(endpoint)
            actions = ([_count_response(0), _retrieval_response(0)] if empty
                       else [TapExecutionError(K.SERVICE_ERROR, "offline")])
            return ArchiveClient(endpoint, executor=FakeTapExecutor(actions), **kwargs)
        result = MirroredArchiveClient(client_factory=factory).search(_spec())
        assert len(calls) == (1 if empty else 3)
        assert result.status is (S.COMPLETE if empty else S.ERROR)
        assert not result.rows
        assert len(result.provenance.mirror_attempts) == len(calls)


@pytest.mark.parametrize("status,kind", [(400,K.QUERY_ERROR),(401,K.QUERY_ERROR),
                                         (403,K.QUERY_ERROR),(408,K.SERVICE_ERROR),
                                         (429,K.SERVICE_ERROR),(503,K.SERVICE_ERROR)])
def test_pyvo_http_errors_preserve_nonretryable_request_failures(status, kind):
    from pyvo.dal.exceptions import DALServiceError
    class Service:
        def run_sync(self, *args, **kwargs):
            raise DALServiceError("service failure", code=status)
    with pytest.raises(TapExecutionError) as exc:
        PyvoTapExecutor(ORIGINS[0]+"/tap", service=Service()).execute("SELECT x", maxrec=1)
    assert exc.value.kind is kind


def test_aq_batch_restarts_all_members_without_mixing_records_or_keys():
    http = Http(
        Reply({"elasticsearchUrl": ORIGINS[0]+"/aq/service/api/search", "elasticsearchApiKey":"eu-key"}),
        Reply(response([hit(label="TP")])), requests.Timeout(),
        Reply({"elasticsearchUrl": ORIGINS[1]+"/aq/service/api/search", "elasticsearchApiKey":"ea-key"}),
        Reply(response([hit(label="12m")])), Reply(response([hit(member=OTHER,label="7m")])),
    )
    result = MirroredArchiveAqClient(client_factory=lambda **kw: ArchiveAqClient(request=http, **kw)).fetch_members(iter([MEMBER,OTHER]))
    assert [r.raw_label for r in result.catalog.records] == ["12m","7m"]
    assert all(r.url.startswith(ORIGINS[1]+"/") for r in result.catalog.records)
    assert result.properties_url == ORIGINS[1]+"/aq/service/api/v1/properties"
    assert [q.member_ous_uid for q in result.queries] == [MEMBER,OTHER]
    assert [a['status'] for a in result.mirror_attempts] == ['FAILED','COMPLETED']
    assert 'eu-key' not in repr(result) and 'ea-key' not in repr(result)
    assert http.calls[1][2]['headers']['Authorization'] == 'ApiKey eu-key'
    assert http.calls[4][2]['headers']['Authorization'] == 'ApiKey ea-key'
    assert [http.calls[i][2]['json']['query']['term']['mous'] for i in [1,2,4,5]] == [MEMBER,OTHER,MEMBER,OTHER]


@pytest.mark.parametrize("status,retries", [(400,False),(401,False),(403,False),(404,False),
                                           (408,True),(429,True),(500,True),(503,True)])
def test_aq_http_retry_policy(status,retries):
    http = Http(Reply({},status), Reply({'elasticsearchUrl': ORIGINS[1]+'/aq/service/api/search'}), Reply(response([])))
    client = MirroredArchiveAqClient(client_factory=lambda **kw: ArchiveAqClient(request=http,**kw))
    if retries:
        result = client.fetch_members([MEMBER])
        assert not result.catalog.records and len(result.mirror_attempts)==2
    else:
        with pytest.raises(ArchiveAqError) as exc: client.fetch_members([MEMBER])
        assert len(exc.value.attempts)==1 and exc.value.http_status==status
        assert len(http.calls)==1


@pytest.mark.parametrize('origin',ORIGINS)
def test_aq_empty_success_and_captured_mirror_provenance(tmp_path,origin):
    from alma_duplicate.archive_array_evidence import load_archive_array_catalog
    data=response([])
    http=Http(Reply({'elasticsearchUrl':origin+'/aq/service/api/search'}),Reply(data))
    result=MirroredArchiveAqClient(origins=(origin,),client_factory=lambda **kw: ArchiveAqClient(request=http,**kw)).fetch_members([MEMBER])
    assert not result.catalog.records and len(result.mirror_attempts)==1
    raw=json.dumps(data).encode();(tmp_path/'aq.json').write_bytes(raw)
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps([{'file':'aq.json','sha256':hashlib.sha256(raw).hexdigest(),
        'url':origin+'/aq/service/api/search/observations/_search','retrieved_at':'2026-10-16T00:00:00+00:00',
        'request_body':{'query':{'term':{'mous':MEMBER}}}}]))
    assert not load_archive_array_catalog(manifest).records


@pytest.mark.parametrize('endpoint',[ORIGINS[1]+'/aq/service/api/search','https://evil.invalid/aq/service/api/search',
                                     ORIGINS[0]+':444/aq/service/api/search'])
def test_discovery_must_stay_on_selected_origin(endpoint):
    http=Http(Reply({'elasticsearchUrl':endpoint,'elasticsearchApiKey':'private-test-key'}))
    with pytest.raises(ArchiveAqError) as exc:
        MirroredArchiveAqClient(client_factory=lambda **kw: ArchiveAqClient(request=http,**kw)).fetch_members([MEMBER])
    assert exc.value.code=='DISCOVERY_INVALID' and len(http.calls)==1
    assert 'private-test-key' not in repr(exc.value.attempts)


def test_aq_all_mirrors_fail_and_contract_errors_are_not_retried():
    http=Http(requests.Timeout(),requests.Timeout(),requests.Timeout())
    with pytest.raises(ArchiveAqError) as exc:
        MirroredArchiveAqClient(client_factory=lambda **kw: ArchiveAqClient(request=http,**kw)).fetch_members([MEMBER])
    assert exc.value.code=='TRANSPORT_ERROR' and len(exc.value.attempts)==3
    http=Http()
    with pytest.raises(ValueError):
        MirroredArchiveAqClient(client_factory=lambda **kw: ArchiveAqClient(request=http,**kw)).fetch_members(['invalid'])
    assert not http.calls


def test_budget_is_request_local_and_caps_network_timeouts():
    now=[0.]
    with request_budget(20,lambda:now[0]):
        assert request_timeout()==(10,10)
        now[0]=18
        assert request_timeout()==(1,1)
        now[0]=20
        with pytest.raises(ArchiveBudgetExpired):request_timeout()
    assert request_timeout()==(10,60)


def test_no_new_mirror_after_budget_expires():
    now=[0.];calls=[]
    def factory(endpoint,**kwargs):
        calls.append(endpoint);now[0]=20
        return ArchiveClient(endpoint,executor=FakeTapExecutor([TapExecutionError(K.SERVICE_ERROR,'timeout')]),**kwargs)
    result=MirroredArchiveClient(budget_seconds=10,clock=lambda:now[0],client_factory=factory).search(_spec())
    assert len(calls)==1 and result.status is S.ERROR
    assert result.provenance.mirror_attempts[-1]['error']=='TIME_BUDGET_EXHAUSTED'
    now[0]=0;calls=[]
    class Aq:
        def fetch_members(self,members):
            now[0]=20
            raise ArchiveAqError('TRANSPORT_ERROR')
    def aq_factory(**kw):calls.append(kw);return Aq()
    with pytest.raises(ArchiveAqError) as exc:
        MirroredArchiveAqClient(budget_seconds=10,clock=lambda:now[0],client_factory=aq_factory).fetch_members([MEMBER])
    assert exc.value.code=='TIME_BUDGET_EXHAUSTED' and len(calls)==1
