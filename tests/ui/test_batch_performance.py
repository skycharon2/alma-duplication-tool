"""Batch diagnostics preserve execution and distinguish unavailable output."""
import pytest
from alma_duplicate.cli.profile_batch import profile_batch
from tests.ui.test_batch_assessment import values, ROW, RAW, runner, run, store as store_fixture

store = store_fixture


@pytest.mark.parametrize('workers', [1, 2])
def test_profile_records_every_branch_and_sources(workers):
    result = profile_batch(values(intents=['LINE']), [ROW], RAW, runner(), workers=workers)
    assert result['execution'] == 'COMPLETED'
    assert len(result['branches']) == 2
    assert result['process_lifetime_peak_rss_bytes'] > 0
    summary = result['summary']
    assert summary['slowest_target']['wall_seconds'] == max(b['wall_seconds'] for b in result['branches'])
    assert summary['stages']['scientific_evaluation']['calls'] == 2
    assert summary['aq_member_queries'] == 0
    for branch in result['branches']:
        assert branch['availability'] == 'AVAILABLE'
        assert branch['files']['report.json'] > 0
        assert branch['sources'] == {'ARCHIVE': 'COMPLETED', 'QUEUE': 'COMPLETED'}
        assert any(s['name'] == 'scientific_evaluation' for s in branch['stages'])
        # Concurrent Archive and Queue stages share elapsed time.
        assert all(0 <= s['self_wall_seconds'] <= s['wall_seconds'] <= branch['wall_seconds']
                   for s in branch['stages'])


def test_profile_compares_aq_worker_counts_without_serializing_member_identifiers(monkeypatch):
    from alma_duplicate.ui.runs import BrowserAssessment

    assess = BrowserAssessment.assess
    worker_counts = []

    def with_aq(self, document):
        worker_counts.append(self.aq_member_workers)
        result = assess(self, document)
        result.document['sources']['ARCHIVE']['array_evidence'] = {'acquisition': {
            'status': 'COMPLETED', 'queries': [{'member_ous_uid': 'uid://A/B/C'}],
        }}
        return result

    monkeypatch.setattr(BrowserAssessment, 'assess', with_aq)
    baseline = profile_batch(values(intents=['LINE']), [ROW], RAW, runner(), workers=2,
                             aq_member_workers=1)
    result = profile_batch(values(intents=['LINE']), [ROW], RAW, runner(), workers=2,
                           aq_member_workers=2)
    assert worker_counts == [1, 1, 2, 2]
    assert result['summary']['aq_member_queries'] == 2
    assert result['summary']['aq_unique_members'] == 1
    assert result['summary']['aq_repeated_member_queries'] == 1
    assert all(b['aq_status'] == 'COMPLETED' and 'aq_members' not in b for b in result['branches'])
    fields = ('source_id', 'purpose', 'retained_contexts', 'branch_outcomes', 'candidate_outcome_sha256')
    assert [tuple(b[key] for key in fields) for b in baseline['branches']] == [
        tuple(b[key] for key in fields) for b in result['branches']]
    assert all(b['retained_contexts'] > 0 and b['branch_outcomes'] for b in result['branches'])


def test_candidate_digest_detects_swapped_outcomes_and_ignores_run_ids_and_order():
    from alma_duplicate.ui.batch_assessment import _candidate_outcome_digest

    def candidate(name, truth, context_id):
        return dict(context_id=context_id, reference={'source': 'ARCHIVE'},
                    display_identity={'Observation ID': name}, branches=[
                        dict(branch='LINE', status=truth, truth=truth, reasons=[], context_id=context_id)])

    first = [candidate('a', 'TRUE', 'run1-a'), candidate('b', 'FALSE', 'run1-b')]
    reordered = [candidate('b', 'FALSE', 'run2-b'), candidate('a', 'TRUE', 'run2-a')]
    swapped = [candidate('a', 'FALSE', 'run2-a'), candidate('b', 'TRUE', 'run2-b')]
    assert _candidate_outcome_digest(first) == _candidate_outcome_digest(reordered)
    assert _candidate_outcome_digest(first) != _candidate_outcome_digest(swapped)


def test_batch_records_tap_mirror_and_fallback_order(monkeypatch, caplog):
    import logging
    from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
    from alma_duplicate.ui.runs import BrowserAssessment

    assess = BrowserAssessment.assess

    def with_live_provenance(self, document):
        result = assess(self, document)
        archive = result.document['sources']['ARCHIVE']
        archive.pop('replay', None)
        archive['source_metadata']['provenance'].update(
            endpoint=ARCHIVE_ORIGINS[1] + '/tap',
            mirror_attempts=[{'origin': ARCHIVE_ORIGINS[0], 'status': 'ERROR'},
                             {'origin': ARCHIVE_ORIGINS[1], 'status': 'COMPLETE'}],
        )
        return result

    monkeypatch.setattr(BrowserAssessment, 'assess', with_live_provenance)
    with caplog.at_level(logging.INFO, logger='alma_duplicate.ui.batch_assessment'):
        output = profile_batch(values(intents=['LINE']), [ROW], RAW, runner(), workers=2)
    for branch in output['branches']:
        tap = branch['archive_tap']
        assert tap['retrieval_seconds'] == round(sum(s['wall_seconds'] for s in branch['stages']
                                                     if s['name'] == 'tap_retrieval'), 3)
        assert {k: v for k, v in tap.items() if k not in ('retrieval_seconds', 'retrieval_phases')} == {
            'connection': 'AUTO', 'source_status': 'COMPLETED', 'region': 'East Asia',
            'attempts': [{'region': 'Europe', 'status': 'ERROR'},
                         {'region': 'East Asia', 'status': 'COMPLETE'}],
        }
    messages = [record.getMessage() for record in caplog.records if 'archive_tap=' in record.getMessage()]
    assert len(messages) == 2 and all('East Asia' in message and 'https://' not in message for message in messages)


def test_tap_phase_summary_excludes_schema_probe_and_counts_only_self_time():
    from types import SimpleNamespace
    from alma_duplicate.ui.batch_assessment import _tap_retrieval_phases

    names_and_parents = [
        ('tap_projection_metadata', None, 0), ('tap_http_headers', 0, 20),
        ('tap_retrieval', None, 0), ('tap_votable', 2, 1),
        ('tap_http_headers', 3, 50), ('tap_http_body_read', 3, 2),
        ('tap_http_body_read', 3, 3), ('tap_materialize', 2, 4),
    ]
    stages = [SimpleNamespace(stage_id=i, name=name, parent_id=parent, self_wall_seconds=elapsed)
              for i, (name, parent, elapsed) in enumerate(names_and_parents)]
    assert _tap_retrieval_phases(stages) == {
        'headers_seconds': 50, 'body_read_seconds': 5,
        'votable_overhead_seconds': 1, 'materialize_seconds': 4,
    }


def test_storage_failure_is_recorded_without_losing_source_status():
    result = profile_batch(values(intents=['LINE']), [ROW], RAW, runner(), max_bytes=1)
    assert result['execution'] == 'INCOMPLETE'
    assert all(r['state'] == 'FAILED' and r['availability'] == 'NO_REPORT' for r in result['branches'])
    assert all(r['sources']['QUEUE'] == 'COMPLETED' for r in result['branches'])
    assert all(any(s['failed'] for s in r['stages']) for r in result['branches'])


def test_observer_failure_cannot_fail_assessment(store):
    def broken(record):
        raise RuntimeError('diagnostic consumer failed')
    batch = run(store, values(intents=['LINE']), performance=broken, max_workers=2)
    assert all(r['state'] == 'COMPLETED' for s in store.batches.get(batch, 'browser-a')['sources']
               for r in s['reports'])


def test_cli_requires_explicit_sources_and_preserves_existing_output(tmp_path):
    from alma_duplicate.cli.profile_batch import main
    setup, targets, output = tmp_path / 'setup', tmp_path / 'targets', tmp_path / 'out'
    args = [str(setup), str(targets), '--sources', 'archive', '--output', str(output)]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    output.write_text('keep')
    with pytest.raises(SystemExit):
        main(args)
    assert output.read_text() == 'keep'
