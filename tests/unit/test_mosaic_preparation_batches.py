"""Bounded scheduling preserves every identity and refuses changed checkpoints."""
import json
import pytest
from alma_duplicate.mosaic_preparation_batches import prepare_batches


def discovery(n=214):
    return dict(schema_version='mosaic_candidate_discovery_1', status='COMPLETED',
        candidates=[dict(context_id=str(i),member_ous_uid=f'M{i}',source_name='S') for i in range(n)])


def worker(discovery, *, output, cache):
    output.mkdir()
    row=discovery['candidates'][0]
    result=dict(row,status='METADATA_ONLY_PREPARED',readiness_status='ARRAY_ACQUIRED')
    if row['member_ous_uid']=='M1':result.update(status='FAILED',error='unavailable')
    report=dict(candidates=[result])
    (output/'preparation.json').write_text(json.dumps(report))
    return report


def run(tmp_path, resume=False, **changes):
    options=dict(discovery=discovery(),output=tmp_path/'run',cache=tmp_path/'cache',
                 max_candidates=100,resume=resume,worker=worker,worker_kwargs={})
    options.update(changes)
    return prepare_batches(**options)


def test_214_candidates_resume_without_dropping_or_retrying_failures(tmp_path):
    first=run(tmp_path)
    assert (first['attempted_count'], first['pending_count'])==(100,114)
    assert len(first['candidates'])==214
    second=run(tmp_path,True)
    assert (second['attempted_count'],second['pending_count'])==(200,14)
    third=run(tmp_path,True)
    assert (third['attempted_count'],third['pending_count'])==(214,0)
    assert third['failed_or_unready_count']==1 and third['status']=='INCOMPLETE'
    assert run(tmp_path,True)==third


def test_receipt_tampering_blocks_resume(tmp_path):
    run(tmp_path)
    (tmp_path/'run/candidate-00000/preparation.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):run(tmp_path,True)


def test_changed_identity_and_uncheckpointed_work_are_not_overwritten(tmp_path):
    run(tmp_path)
    with pytest.raises(ValueError,match='changed'):run(tmp_path,True,discovery=discovery(213))
    (tmp_path/'run/candidate-00100').mkdir()
    with pytest.raises(ValueError,match='Uncheckpointed'):run(tmp_path,True)


@pytest.mark.parametrize('budget',[0,101,True])
def test_invalid_budget(tmp_path,budget):
    with pytest.raises(ValueError):run(tmp_path,max_candidates=budget)
    assert not (tmp_path/'run').exists()


def test_main_resume_preserves_pending_and_skips_metadata(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from alma_duplicate.mosaic_backend import run_mosaic_backend
    from alma_duplicate.mosaic_candidate_discovery import plan_discovery
    from alma_duplicate.proposed_mosaic import import_proposed
    proposed=import_proposed(b'RA,Dec,Coordinate Type,Coordinate Units\n--\n0,0,Absolute,Degrees\n',
        source_name='S',array='12m',confirm_fixed_icrs=True,confirm_complete=True)
    d=discovery(1);d['plan']=plan_discovery(proposed,margin_arcsec=1)
    saved=tmp_path/'saved';saved.mkdir();(saved/'discovery.json').write_text(json.dumps(d))
    def preparation(value,**kwargs):
        assert value==d and kwargs['resume'] is True
        return dict(status='INCOMPLETE',candidates=[dict(d['candidates'][0],status='PENDING')])
    def forbidden(spec):raise AssertionError('Pending candidates must not query metadata')
    r=run_mosaic_backend(None,legacy_mosaic_input(proposed,tmp_path/'assessment',tmp_path/'cache',1,
        preparation_directory=saved),archive_client=SimpleNamespace(search=forbidden),preparation_provider=preparation)
    assert r['assessment_status']=='INCOMPLETE'
    assert r['candidates'][0]['status']=='PENDING'
    with pytest.raises(ValueError,match='differs'):
        run_mosaic_backend(None,legacy_mosaic_input(proposed,tmp_path/'wrong',tmp_path/'cache',2,
            preparation_directory=saved),preparation_provider=preparation)


def test_resume_retains_measured_elapsed_and_cache_counts(tmp_path):
    def cached_worker(*args,**kwargs):
        report=worker(*args,**kwargs)
        report['candidates'][0]['reused_cache']=True
        return report
    first=run(tmp_path,max_candidates=1,worker=cached_worker)
    elapsed=first['candidates'][0]['preparation_elapsed_seconds']
    second=run(tmp_path,True,max_candidates=1,worker=cached_worker)
    assert second['candidates'][0]['preparation_elapsed_seconds']==elapsed
    assert second['measured_candidate_count']==2
    assert second['measured_candidate_seconds']>=elapsed>=0
    assert second['reused_package_count']==2
    assert second['prepared_count']==1
    assert second['failed_or_unready_count']==1


def legacy_mosaic_input(*args, **kwargs):
    from alma_duplicate.mosaic_backend import MosaicAssessmentInput
    return MosaicAssessmentInput(*args, coverage_model="RECONSTRUCTED", **kwargs)
