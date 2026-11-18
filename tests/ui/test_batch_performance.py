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
    for branch in result['branches']:
        assert branch['availability'] == 'AVAILABLE'
        assert branch['files']['report.json'] > 0
        assert branch['sources'] == {'ARCHIVE': 'COMPLETED', 'QUEUE': 'COMPLETED'}
        assert any(s['name'] == 'scientific_evaluation' for s in branch['stages'])
        assert sum(s['self_wall_seconds'] for s in branch['stages']) <= branch['wall_seconds']


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
