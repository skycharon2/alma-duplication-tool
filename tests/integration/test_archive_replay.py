"""Real NGC6240 response replay; never an expected-UID selection fixture."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import shutil

import pytest
from alma_duplicate.cli.evaluate import main
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import build_search_plan

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT/'tests/fixtures/archive/ngc6240/manifest.json'
REQUEST = ROOT/'examples/dual_source/request.json'
QUEUE = ROOT/'tests/fixtures/queue/queue_pipeline_v1.csv'


def spec():
    p=json.loads(REQUEST.read_text())
    v=validate_proposed_observation(p['request'],p['search_options'])
    return build_search_plan(v,queue_candidate_beam=True).for_source('ARCHIVE').archive_query


def arguments(output, manifest=CAPTURE, request=REQUEST):
    return ['--request',str(request),'--queue-csv',str(QUEUE),'--archive-replay',str(manifest),
            '--queue-candidate-beam','--output',str(output)]


def test_real_dual_source_cli_no_network(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**k: pytest.fail('network access'))
    out=tmp_path/'report.json'
    assert main(arguments(out)) == 0
    p=json.loads(out.read_text());a=p['sources']['ARCHIVE'];q=p['sources']['QUEUE']
    assert a['status'] == q['status'] == 'COMPLETED'
    assert a['query_binding']['status'] == 'MATCHED'
    provenance=a['source_metadata']['provenance']
    assert provenance['expected_count'] == provenance['retrieved_count'] == 144
    assert provenance['started_at'] == json.loads(CAPTURE.read_text())['started_at']
    assert a['replay']['manifest_sha256'] == hashlib.sha256(CAPTURE.read_bytes()).hexdigest()
    assert q['source_metadata']['snapshot']['snapshot_sha256'] == hashlib.sha256(QUEUE.read_bytes()).hexdigest()
    assert p['evaluation_scope']['evaluated_contexts'] == p['evaluation_scope']['total_retained'] == 157
    assert p['evaluation_scope']['shown_candidates'] == 1
    contexts=p['context_evaluations']
    archive=[c for c in contexts if c['reference']['source']=='ARCHIVE']
    queue=[c for c in contexts if c['reference']['source']=='QUEUE']
    assert len(archive) == 144 and len(queue) == 13
    assert all(c['criteria'][1]['outcome'] is None and c['criteria'][1]['issues'] for c in archive)
    assert queue[0]['criteria'][1]['outcome'] == 'SATISFIED'
    assert a['filter_summary']['predicates'][0]['outcomes']=={'MATCH':96,'NOT_EVALUATED':48}
    assert q['filter_summary']['predicates'][0]['outcomes']=={'MATCH':1,'NOT_EVALUATED':12}
    assert p['assessment']=='NOT_AGGREGATED'


def copy_capture(tmp_path):
    folder=tmp_path/'capture';shutil.copytree(CAPTURE.parent,folder)
    return folder/'manifest.json'


def test_checksum_corruption_rejected(tmp_path):
    m=copy_capture(tmp_path)
    with (m.parent/'response-2.xml').open('ab') as f: f.write(b'changed')
    assert main(arguments(tmp_path/'report.json',m)) == 2
    assert not (tmp_path/'report.json').exists()


def test_different_cone_is_failed_source_not_silent_reuse(tmp_path):
    p=json.loads(REQUEST.read_text())
    p['search_options']['radius']['value']=20
    r=tmp_path/'request.json';r.write_text(json.dumps(p))
    out=tmp_path/'report.json'
    assert main(arguments(out,request=r)) == 3
    p=json.loads(out.read_text())
    assert p['sources']['ARCHIVE']['status']=='FAILED'
    assert p['sources']['QUEUE']['status']=='COMPLETED'
    assert not p['sources']['ARCHIVE']['rows']


def test_live_and_replay_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(arguments(tmp_path/'out.json')+['--live-archive'])
    assert exc.value.code==2


@pytest.mark.parametrize('payload',[{},[],{'replay_version':'999'}])
def test_invalid_manifest(tmp_path,payload):
    m=tmp_path/'manifest.json';m.write_text(json.dumps(payload))
    assert main(arguments(tmp_path/'out.json',m))==2


def test_manifest_cannot_traverse_directories(tmp_path):
    m=copy_capture(tmp_path);p=json.loads(m.read_text());p['responses'][0]['file']='../response.xml'
    m.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='sibling'):
        RecordedArchiveClient(m)


def test_response_cannot_be_overwritten(tmp_path):
    m=copy_capture(tmp_path);response=m.parent/'response-2.xml';before=response.read_bytes()
    assert main(arguments(response,m)+['--overwrite'])==2
    assert response.read_bytes()==before


def test_incomplete_response_never_claims_complete(tmp_path):
    m=copy_capture(tmp_path);p=json.loads(m.read_text());entry=p['responses'][-1]
    response=m.parent/entry['file']
    data=response.read_bytes().replace(b'value="OK"',b'value="OVERFLOW"')
    assert data!=response.read_bytes()
    response.write_bytes(data);entry['sha256']=hashlib.sha256(data).hexdigest();m.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='completeness'):
        RecordedArchiveClient(m).search(spec())


def test_all_responses_must_be_consumed(tmp_path):
    m=copy_capture(tmp_path);p=json.loads(m.read_text());p['responses'].append(p['responses'][0]);m.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='full capture'):
        RecordedArchiveClient(m).search(spec())


def test_metadata_and_original_counts_preserved():
    r=RecordedArchiveClient(CAPTURE).search(spec())
    assert r.is_complete and len(r.rows)==144
    fields={f.name:f for f in r.field_metadata}
    assert fields['s_ra'].unit=='deg'
    assert fields['spatial_resolution'].unit=='arcsec'
    assert 's_region' in fields and 'frequency_support' in fields
    assert len(r.provenance.projection.probe_rows)==6
