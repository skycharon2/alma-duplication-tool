"""Rectangle science preserves numerical policy and source/array isolation."""
from dataclasses import replace
import json
import pytest

from alma_duplicate.queue_rectangle_science import assess_queue_rectangle_science
from tests.integration.test_queue_custom_science import (candidate as custom_candidate, request,
    pointings, science, rule, line_request)


def candidate(changes=None, rows=2):
    return custom_candidate({'Mosaic':'Rectangle', 'Mos. Length':'1', 'Mos. Width':'1',
        'Mos. Spacing':'20', 'Mos. PA':'0', 'Long Offset':'0', 'Lat Offset':'0', **(changes or {})},rows=rows)


def test_continuum_requested_rms_and_duplicate_rows():
    req,_=request()
    r=assess_queue_rectangle_science(candidate(),req,pointings(req,basis='PER_POINTING'))
    assert len(r['candidates'])==2
    assert len({c['candidate_id'] for c in r['candidates']})==2
    for c in r['candidates']:
        s=c['science']
        assert s['matching_arrays_by_intent']['CONTINUUM']==[7.,12.]
        assert s['branches'][0]['truth']=='TRUE'
        rms=rule(s['variants'][0],'CONT-RMS')
        assert rms['candidate']['value']==.15
        assert dict(rms['details'])['candidate_mosaic_rms_basis']=='RECTANGLE_COMBINED_IMAGE_REQUEST'
        assert dict(rms['details'])['rms_basis_conversion']=='NONE'
        assert s['source_row_id']==c['geometry']['source_row_id']
    json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('changes,truth',[
    ({'Ref.Frequency':'100'},'FALSE'),
    ({'Mos. Coord.':'galactic'},'UNKNOWN'),
    ({'Req.Sensitivity':'100'},'FALSE'),
])
def test_rejection_and_unresolved(changes,truth):
    req,_=request()
    r=assess_queue_rectangle_science(candidate(changes),req,pointings(req))
    assert science(r)['branches'][0]['truth']==truth


def test_line_same_spw_and_no_mode_borrowing():
    req=replace(line_request(center_ghz=226.,resolution_kms=20),geometry='MOSAIC')
    changes={'Project Code':'2024.1.00001.S','Polarization':'DOUBLE','Req.Sensitivity':'.001','Spec.Res. SPW 1':'.9765625'}
    r=assess_queue_rectangle_science(candidate(changes),req,pointings(req))
    assert science(r)['matching_arrays_by_intent']['LINE']==[7.,12.]
    for c in r['candidates']:
        for v in c['science']['variants']:
            passing=[p for p in v['line_pairs'] if p['truth']=='TRUE']
            assert passing and all(p['reference']['spw_number']==1 for p in passing)
            assert all(p['reference']['source_row_id']==c['geometry']['source_row_id'] for p in passing)
    r=assess_queue_rectangle_science(candidate(changes|{'Spec.Res. SPW 1':'31.25'}),req,pointings(req))
    assert science(r)['branches'][0]['truth']=='FALSE'


def test_context_binding_and_budget(monkeypatch):
    req,_=request()
    p=pointings(req);p['setup_id']='foreign'
    with pytest.raises(ValueError,match='target and setup'):
        assess_queue_rectangle_science(candidate(),req,p)
    monkeypatch.setattr('alma_duplicate.queue_mosaic_row_science.MAX_SPECTRAL_PAIRS',1)
    with pytest.raises(ValueError,match='budget'):
        assess_queue_rectangle_science(candidate(),req,pointings(req))


def test_wrong_geometry_contract_is_not_accepted():
    from alma_duplicate.rules.queue_common import queue_mosaic_common_matches_kind
    from alma_duplicate.domain.queue import QueueMosaicKind
    from alma_duplicate.queue_mosaic_row_science import _common
    from alma_duplicate.queue_rectangle_science import DECISION
    from alma_duplicate.queue_rectangle_backend import assess_queue_rectangle_csv
    from alma_duplicate.comparison import build_queue_contexts
    req,_=request();src=candidate()
    pos=assess_queue_rectangle_csv(src,pointings(req))['candidates'][0]['position']['beam_variants'][0]
    common=_common(req,build_queue_contexts(src).contexts[0],pos,'rectangle',DECISION)
    assert queue_mosaic_common_matches_kind(common,QueueMosaicKind.RECTANGULAR_MOSAIC)
    assert not queue_mosaic_common_matches_kind(common,QueueMosaicKind.CUSTOM_POINTING)


def test_mixed_array_position_and_no_complementary_science_borrowing(monkeypatch):
    import alma_duplicate.queue_mosaic_row_science as backend
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    from alma_duplicate.rules.model import CriterionOutcome as O
    req,_=request();p=pointings(req)
    p['points'][0]['dec_deg']+=(primary_beam_fwhm_deg(230,7)+primary_beam_fwhm_deg(230,12))/4
    r=assess_queue_rectangle_science(candidate(),req,p)
    assert science(r)['matching_arrays_by_intent']['CONTINUUM']==[7.]
    original=backend.evaluate_queue_continuum
    def numerical(request, context, common, **kw):
        freq,rms=original(request,context,common,**kw)
        d=dict(common[1].derived)['antenna_diameter_m']
        return freq,replace(rms,outcome=O.NOT_SATISFIED if d==7 else O.SATISFIED)
    monkeypatch.setattr(backend,'evaluate_queue_continuum',numerical)
    r=assess_queue_rectangle_science(candidate(),req,p)
    assert science(r)['branches'][0]['truth']=='FALSE'


def test_independent_spectral_rows_and_unresolved_rms():
    from tests.integration.test_candidate_search import queue_rows
    src=candidate()
    rows=[dict(zip(r.raw_row.declared_columns,r.raw_row.raw_values)) for r in src.row_inputs]
    rows[1]['Ref.Frequency']='100'
    req,_=request()
    r=assess_queue_rectangle_science(queue_rows(*rows),req,pointings(req))
    assert sorted(c['science']['branches'][0]['truth'] for c in r['candidates'])==['FALSE','TRUE']
    # An unsupported usable-bandwidth mapping keeps the existing RMS rule unknown.
    r=assess_queue_rectangle_science(candidate({'Bandwidth SPW 1':'123'}),req,pointings(req))
    assert rule(science(r)['variants'][0],'CONT-RMS')['outcome'] is None
