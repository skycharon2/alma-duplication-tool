from copy import deepcopy
import pytest
from test_ot_pointings import proposed
from test_mosaic_coverage_union import ready
from alma_duplicate.assessment import assess_mosaic_candidates


def candidate(name='one', offset=0):
    r=ready(offset)
    return dict(context_id=name,member_ous_uid=r['member_ous_uid'],source_name=r['source_name'],
                readiness=r,selections=[dict(asdm_uid='A',spw_id=16)])


def run(p, candidates):
    return assess_mosaic_candidates(p,candidates,assume_uniform_field_antennas=True)


def test_satisfied_shared_contract_and_missing_evidence():
    c=candidate(); missing=dict(context_id='missing',member_ous_uid='other',source_name='S')
    rows=run(proposed('0,0,Absolute,Degrees'),[c,missing])['candidates']
    assert rows[0]['criteria'][0]['criterion_id']=='POS-MOSAIC'
    assert rows[0]['criteria'][0]['outcome']=='SATISFIED'
    assert rows[1]['criteria'][0]['evaluation']=='INSUFFICIENT_INFORMATION'
    assert rows[1]['criteria'][0]['outcome'] is None
    assert rows[0]['duplication_status']=='NOT_EVALUATED'


def test_candidates_never_share_coverage():
    a=candidate();b=deepcopy(a);b['context_id']='two'
    b['readiness']['executions'][0]['fields'][0]['ra_deg']=1
    rows=run(proposed('0,0,Absolute,Degrees\n1,0,Absolute,Degrees'),[a,b])['candidates']
    assert all(r['coverage']['covered_fraction_lower']==.5 for r in rows)
    assert all(r['criteria'][0]['outcome'] is None for r in rows)
    assert all('COMPLETENESS_REQUIRED' in r['criteria'][0]['reasons'][0] for r in rows)


def test_binding_conflicts_and_duplicate_candidate_identity():
    c=candidate();c['member_ous_uid']='wrong'
    with pytest.raises(ValueError,match='different candidate'):run(proposed('0,0,Absolute,Degrees'),[c])
    with pytest.raises(ValueError,match='unique'):run(proposed('0,0,Absolute,Degrees'),[candidate(),candidate()])


def test_incomplete_proposed_list_is_not_positive():
    r=run(proposed('0,0,Absolute,Degrees',False),[candidate()])['candidates'][0]['criteria'][0]
    assert r['outcome'] is None and r['reasons']==('PROPOSED_POINTING_COMPLETENESS_REQUIRED',)
