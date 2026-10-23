import json
import pytest
from test_mosaic_coverage_union import ready
from test_ot_pointings import raw
from alma_duplicate import mosaic_assessment_input as loader
from alma_duplicate.cli.mosaic_assessment import main


def write(tmp_path,rows):
    p=tmp_path/'candidates.json'
    p.write_text(json.dumps(dict(schema_version='mosaic_candidates_1',candidates=rows)))
    return p


def row():
    return dict(context_id='A',member_ous_uid='M',source_name='S')


def test_missing_evidence_remains_a_candidate(tmp_path):
    candidates,digest=loader.load_candidates(write(tmp_path,[row()]))
    assert candidates==[row()] and len(digest)==64


def test_relative_paths_and_verified_binding(tmp_path,monkeypatch):
    calls=[]
    def build(directory,*,array_catalog):
        calls.append((directory,array_catalog));return ready()
    monkeypatch.setattr(loader,'build_readiness',build)
    r=dict(row(),package_audit_dir='audit',array_catalog='array.json',selections=[dict(asdm_uid='A',spw_id=16)])
    result,_=loader.load_candidates(write(tmp_path,[r]))
    assert calls==[(tmp_path/'audit',tmp_path/'array.json')]
    assert result[0]['readiness']['member_ous_uid']=='M'
    r['member_ous_uid']='wrong'
    with pytest.raises(ValueError,match='another candidate'):loader.load_candidates(write(tmp_path,[r]))


@pytest.mark.parametrize('rows',[[],[row(),row()],[dict(row(),package_audit_dir='audit')],
    [dict(row(),readiness={})],[dict(row(),context_id='')]])
def test_bad_manifests(tmp_path,rows):
    with pytest.raises(ValueError):loader.load_candidates(write(tmp_path,rows))


def test_cli_reports_missing_candidate_and_refuses_overwrite(tmp_path):
    p=tmp_path/'points.txt';p.write_bytes(raw('0,0,Absolute,Degrees'))
    out=tmp_path/'out.json'
    args=['--pointings',str(p),'--source','proposed','--array','12m','--confirm-fixed-icrs',
          '--confirm-complete','--candidates',str(write(tmp_path,[row()])),
          '--hpbw-coefficient','1.13','--boundary-epsilon-arcsec','0.000001','--output',str(out)]
    assert main(args)==0
    report=json.loads(out.read_text())
    assert report['candidates'][0]['criteria'][0]['evaluation']=='INSUFFICIENT_INFORMATION'
    assert report['proposed']['row_count']==1
    with pytest.raises(SystemExit):main(args)


def test_duplicate_json_keys_rejected(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"schema_version":"mosaic_candidates_1","candidates":[],"candidates":[]}')
    with pytest.raises(ValueError,match='Duplicate JSON key'):loader.load_candidates(p)
