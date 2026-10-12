"""Retrieval-first completeness preserves strict count fallback and row identity."""
from dataclasses import replace
import io

import pytest
from astropy.io.votable import parse
from pyvo.dal import TAPResults
from pyvo.dal.exceptions import DALQueryError

from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus, TapExecutionError, ArchiveQueryErrorKind
from alma_duplicate.performance import PerformanceRecorder
from tests.fakes import FakeTapExecutor
from tests.unit.test_archive_client import _count_response, _retrieval_response, _spec
from tests.unit.test_tap_executor import _FakeService


def run(response, *fallback, maxrec=10):
    executor = FakeTapExecutor([response, *fallback])
    client = ArchiveClient('https://example.invalid/tap', executor=executor,
                           maxrec=maxrec, completeness_policy='STATUS_THEN_COUNT')
    return client.search(_spec()), executor


@pytest.mark.parametrize('size', [0, 1, 9])
def test_explicit_complete_below_cap_skips_count_without_inventing_total(size):
    response = replace(_retrieval_response(size), explicit_success=True)
    with PerformanceRecorder().record() as timings:
        result, executor = run(response)
    assert result.status == ArchiveQueryStatus.COMPLETE
    assert result.rows == response.rows
    assert result.field_metadata == response.field_metadata
    assert result.provenance.expected_count is None
    assert result.provenance.count_query_status_raw is None
    assert 'COUNT(*)' in result.provenance.count_adql
    assert result.provenance.count_attempted is False
    assert result.provenance.completeness_policy == 'STATUS_THEN_COUNT'
    assert result.provenance.retrieved_count == size
    assert len(executor.calls) == 1
    assert executor.calls[0].maxrec == 10
    assert 'COUNT' not in executor.calls[0].adql
    assert 'tap_count' not in [s.name for s in timings.stages]


@pytest.mark.parametrize('status,total,expected', [
    ('OK', 10, 'COMPLETE'), ('OK', 11, 'COUNT_MISMATCH'),
    ('OVERFLOW', 10, 'OVERFLOW'), ('OVERFLOW', 11, 'OVERFLOW'),
    (None, 10, 'ERROR'), ('unexpected', 10, 'ERROR'),
])
def test_cap_or_bad_status_still_requires_count_and_never_hides_overflow(status, total, expected):
    result, executor = run(replace(_retrieval_response(10, status=status), explicit_success=True),
                           _count_response(total))
    assert result.status == expected
    assert result.can_reconstruct == (expected == 'COMPLETE')
    assert len(executor.calls) == 2
    assert 'COUNT(*)' in executor.calls[-1].adql
    assert result.provenance.expected_count == total


@pytest.mark.parametrize('size,status,explicit', [(1, 'OVERFLOW', True), (1, None, True),
                                                (1, 'OK', False), (0, 'OK', False)])
def test_small_result_alone_does_not_establish_completeness(size, status, explicit):
    result, executor = run(replace(_retrieval_response(size, status=status), explicit_success=explicit),
                           _count_response(size + 1))
    assert not result.can_reconstruct
    assert len(executor.calls) == 2


def test_schema_checked_even_for_empty_explicit_success():
    result, executor = run(replace(_retrieval_response(0, declared_columns=('obs_id',)),
                                   explicit_success=True), _count_response(0))
    assert result.error_kind == ArchiveQueryErrorKind.SCHEMA_DRIFT
    assert not result.can_reconstruct
    assert len(executor.calls) == 2


@pytest.mark.parametrize('error', [_count_response(-1), _count_response(1, status='OVERFLOW'),
                                  TapExecutionError(ArchiveQueryErrorKind.SERVICE_ERROR, 'timeout')])
def test_fallback_count_failure_keeps_diagnostic_rows_but_blocks_reconstruction(error):
    result, _ = run(replace(_retrieval_response(10), explicit_success=True), error)
    assert result.status == 'ERROR'
    assert len(result.rows) == 10
    assert not result.can_reconstruct


def test_retrieval_failure_does_not_issue_count():
    result, executor = run(TapExecutionError(ArchiveQueryErrorKind.SERVICE_ERROR, 'timeout'))
    assert result.status == 'ERROR'
    assert 'COUNT(*)' in result.provenance.count_adql
    assert result.provenance.count_attempted is False
    assert len(executor.calls) == 1


def test_equal_rows_are_not_deduplicated_and_query_policy_has_distinct_hash():
    response = replace(_retrieval_response(1), explicit_success=True)
    response = replace(response, rows=response.rows * 2)
    fast, _ = run(response)
    legacy = ArchiveClient('https://example.invalid/tap', maxrec=10,
                           executor=FakeTapExecutor([_count_response(2), response])).search(_spec())
    assert fast.rows == legacy.rows
    assert len(fast.rows) == 2
    assert fast.status == legacy.status
    assert fast.provenance.retrieval_adql == legacy.provenance.retrieval_adql
    assert fast.provenance.query_hash != legacy.provenance.query_hash


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError, match='completeness policy'):
        ArchiveClient('https://example.invalid/tap', completeness_policy='assume')


@pytest.mark.parametrize('before,after,explicit,status', [
    ('OK', None, True, 'OK'), ('OK', 'OK', True, 'OK'),
    ('OK', 'OVERFLOW', False, 'OVERFLOW'), (None, None, False, None),
])
def test_real_votable_status_including_trailing_overflow_and_pyvo_default(before, after, explicit, status):
    def info(value):
        return '' if value is None else f'<INFO name="QUERY_STATUS" value="{value}"/>'
    xml = f'''<?xml version="1.0"?>
    <VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
    <RESOURCE type="results">{info(before)}
    <TABLE><FIELD name="obs_id" datatype="char" arraysize="*"/>
    <DATA><TABLEDATA><TR><TD>same-row</TD></TR></TABLEDATA></DATA></TABLE>
    {info(after)}</RESOURCE></VOTABLE>'''
    result = TAPResults(parse(io.BytesIO(xml.encode())))
    executor = PyvoTapExecutor('https://example.invalid/tap', service=_FakeService(result=result))
    response = executor.execute('SELECT obs_id FROM ivoa.obscore', maxrec=10)
    assert response.query_status_raw == status
    assert response.explicit_success is explicit


def test_trailing_error_and_truncated_xml_cannot_reach_success():
    for xml in [b'<VOTABLE><RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>',
                b'<VOTABLE><RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>'
                b'<TABLE><FIELD name="x" datatype="int"/><DATA><TABLEDATA/></DATA></TABLE>'
                b'<INFO name="QUERY_STATUS" value="ERROR">failed</INFO></RESOURCE></VOTABLE>']:
        with pytest.raises((ValueError, DALQueryError)):
            TAPResults(parse(io.BytesIO(xml)))


def test_shared_assessment_accepts_count_omission_and_still_fetches_aq():
    from alma_duplicate.assessment import ArchiveInput, AssessmentSources, assess_observation
    from tests.integration.test_auto_retrieval import auto_payload
    from tests.integration.test_live_aq_assessment import tap_rows, fetcher, acquisition
    from alma_duplicate.clients.archive_contract import TapResponse

    source, members = tap_rows()
    response = TapResponse(source.rows, tuple(f.name for f in source.field_metadata),
                           source.field_metadata, 'OK', explicit_success=True)
    catalog = fetcher(members)(members)
    documents = []
    for policy in ['COUNT_FIRST', 'STATUS_THEN_COUNT']:
        responses = [response] if policy == 'STATUS_THEN_COUNT' else [_count_response(len(source.rows)), response]
        executor = FakeTapExecutor(responses)
        client = ArchiveClient('https://example.invalid/tap', executor=executor,
                               completeness_policy=policy, run_id_factory=lambda: 'same-run')
        calls = []
        def aq(requested):
            calls.append(requested)
            return catalog
        result = assess_observation(**auto_payload(), sources=AssessmentSources(
            'LIVE', lambda: ArchiveInput(client), archive_array_fetcher=aq))
        assert result.status == 'COMPLETED'
        assert acquisition(result)['status'] == 'COMPLETED'
        assert calls == [members]
        assert len(result.document['context_evaluations']) == 3
        documents.append(result.document)
    assert documents[0]['context_evaluations'] == documents[1]['context_evaluations']
