import json
import pytest
from test_ot_pointings import proposed
from alma_duplicate.mosaic_candidate_discovery import plan_discovery, discover_candidates


def response(rows=(),status='OK'):
    names=['proposal_id','member_ous_uid','asdm_uid','target_name','science_observation','is_mosaic']
    return ('<VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE type="results">'
        f'<INFO name="QUERY_STATUS" value="{status}"/><TABLE>'+''.join(f'<FIELD name="{n}"/>' for n in names)
        +'<DATA><TABLEDATA>'+''.join('<TR>'+''.join(f'<TD>{v}</TD>' for v in row)+'</TR>' for row in rows)
        +'</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>').encode()


def p(count=1):
    return proposed('\n'.join(f'{i},-30,Absolute,Degrees' for i in range(count)))


def test_all_points_chunked_and_no_center_filter():
    plan=plan_discovery(p(21),margin_arcsec=2)
    assert len(plan['requests'])==3
    assert sum(len(r['proposed_ids']) for r in plan['requests'])==21
    assert all('s_ra' not in r['query'] for r in plan['requests'])
    assert all('s_region IS NULL' not in r['query'] for r in plan['requests'][:-1])
    assert plan['requests'][-1]['kind']=='NULL_REGION_FALLBACK'
    assert "CIRCLE('ICRS',20,-30," in plan['requests'][1]['query']


def test_zero_margin_wrap_and_duplicate_rows():
    data=proposed('359.999,-89,Absolute,Degrees\n0.001,-89,Absolute,Degrees\n0.001,-89,Absolute,Degrees')
    q=plan_discovery(data,margin_arcsec=0)['requests'][0]
    assert q['query'].count('CONTAINS(')==2 and len(q['proposed_ids'])==3


def test_group_by_member_target_preserve_executions(tmp_path):
    rows=[('P','M','E1','S','T','T'),('P','M','E2','S','T','T'),('P','M','E1','OTHER','T','T')]
    r=discover_candidates(p(21),tmp_path/'run',margin_arcsec=1,fetch=lambda url:(200,response(rows)))
    assert r['status']=='COMPLETED' and len(r['candidates'])==2
    g=next(c for c in r['candidates'] if c['source_name']=='S')
    assert g['asdm_uids']==['E1','E2'] and g['request_indices']==[0,1,2]
    assert r['plan']['recall_status'].startswith('NOT_ESTABLISHED')
    assert json.loads((tmp_path/'run/candidates.json').read_text())['schema_version']=='mosaic_candidates_1'


@pytest.mark.parametrize('failure',[(200,response(status='OVERFLOW')),(403,b'denied'),(200,b'bad')])
def test_partial_failures_are_not_empty_success(tmp_path,failure):
    replies=iter([(200,response([('P','M','E','S','T','T')])),failure,(200,response())])
    r=discover_candidates(p(21),tmp_path/'run',margin_arcsec=0,fetch=lambda url:next(replies))
    assert r['status']=='INCOMPLETE' and r['candidate_count']==1
    assert r['requests'][1]['status']=='FAILED'


def test_empty_success_not_nonduplication(tmp_path):
    r=discover_candidates(p(),tmp_path/'run',margin_arcsec=0,fetch=lambda url:(200,response()))
    assert r['status']=='COMPLETED' and r['candidate_count']==0
    assert r['absence_interpretation']=='NO_DUPLICATION_CONCLUSION_FROM_EMPTY_SEARCH'


@pytest.mark.parametrize('margin',[-1,float('nan'),3601,True])
def test_invalid_margin(margin):
    with pytest.raises(ValueError):plan_discovery(p(),margin_arcsec=margin)


def test_all_geometries_preserved_without_weakening_package_parser(tmp_path):
    from alma_duplicate.archive_mosaic_pipeline import read_mosaic_rows
    rows=[('P','M','E1','S','T','T'),('P','M','E2','S','T','F'),
          ('P','N','E3','OTHER','T','F'),('P','U','E4','UNKNOWN','T','')]
    raw=response(rows)
    result=discover_candidates(p(),tmp_path/'run',margin_arcsec=1,fetch=lambda url:(200,raw))
    assert result['status']=='COMPLETED'
    flags={c['member_ous_uid']:c['geometry_flags'] for c in result['candidates']}
    assert flags=={'M':['F','T'],'N':['F'],'U':['']}
    with pytest.raises(ValueError):read_mosaic_rows(raw)
    assert all("is_mosaic='T'" not in req['query'] for req in result['plan']['requests'])


def test_mirror_fallback_restarts_whole_discovery_and_preserves_receipts(tmp_path):
    from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
    calls = []
    replies = iter([(200, response([('P', 'OLD', 'E', 'S', 'T', 'T')])),
                    (503, b'unavailable'),
                    (200, response([('P', 'NEW', 'E', 'S', 'T', 'F')])),
                    (200, response())])
    def fetch(url):
        calls.append(url)
        return next(replies)
    report = discover_candidates(p(), tmp_path/'run', margin_arcsec=1,
                                 origins=ARCHIVE_ORIGINS, fetch=fetch)
    assert report['status'] == 'COMPLETED'
    assert [c['member_ous_uid'] for c in report['candidates']] == ['NEW']
    assert [a['status'] for a in report['mirror_attempts']] == ['INCOMPLETE', 'COMPLETED']
    assert all(url.startswith(ARCHIVE_ORIGINS[1]) for url in calls[2:])
    for receipt in report['requests']:
        assert (tmp_path/'run'/receipt['response_file']).is_file()
    assert json.loads((tmp_path/'run/discovery.json').read_text()) == report
    assert (tmp_path/'run/mirror-00/discovery.json').is_file()


@pytest.mark.parametrize('origins_count', [1, 3])
def test_completed_empty_mirror_stops_without_false_negative(tmp_path, origins_count):
    from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
    calls = []
    def fetch(url):
        calls.append(url)
        return 200, response()
    report = discover_candidates(p(), tmp_path/'run', margin_arcsec=1,
                                 origins=ARCHIVE_ORIGINS[:origins_count], fetch=fetch)
    assert len(calls) == 2
    assert len(report['mirror_attempts']) == 1
    assert report['status'] == 'COMPLETED'
    assert report['absence_interpretation'] == 'NO_DUPLICATION_CONCLUSION_FROM_EMPTY_SEARCH'


@pytest.mark.parametrize('origins_count', [1, 3])
def test_failed_mirrors_keep_partial_evidence_without_merging(tmp_path, origins_count):
    from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
    calls = []
    def fetch(url):
        calls.append(url)
        if len(calls) % 2 == 0:
            return 503, b'unavailable'
        return 200, response([('P', str(len(calls)), 'E', 'S', 'T', 'T')])
    report = discover_candidates(p(), tmp_path/'run', margin_arcsec=1,
                                 origins=ARCHIVE_ORIGINS[:origins_count], fetch=fetch)
    assert report['status'] == 'INCOMPLETE'
    assert report['candidate_count'] == 1
    assert len(report['mirror_attempts']) == origins_count
    assert len(calls) == 2 * origins_count
