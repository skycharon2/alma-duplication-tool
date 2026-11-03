"""Position-only adapter integration with the existing strict-majority rule."""
import csv
import io
from dataclasses import replace
from pathlib import Path

import pytest
from astropy.coordinates import SkyCoord
from astropy import units as u

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_rectangle_backend import assess_queue_rectangle_csv
from alma_duplicate.geometry import primary_beam_fwhm_deg


def source(frame='ICRS'):
    text = (Path(__file__).parents[1]/'fixtures/queue/queue_pipeline_v1.csv').read_text()
    prefix, table = text.split('Project Code,Target Name,', 1)
    reader = csv.DictReader(io.StringIO('Project Code,Target Name,'+table))
    rows = list(reader)
    for row in rows:
        if row['Mosaic'] == 'Rectangle':
            row.update(RA='150', Dec='0', **{'Mos. Length':'1', 'Mos. Width':'1',
                'Mos. Spacing':'20', 'Mos. PA':'0', 'Mos. Coord.':frame,
                'Long Offset':'0', 'Lat Offset':'0', 'Use 7-m?':'True',
                'Req. Ang. Res.':'1', 'Ref.Frequency':'100'})
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader(); writer.writerows(rows)
    parsed = parse_queue_csv_bytes((prefix+out.getvalue()).encode())
    assert parsed.can_reconstruct
    return parsed


def proposal(inside, total):
    return dict(frame_basis='USER_CONFIRMED_FIXED_ICRS', completeness='USER_CONFIRMED_COMPLETE',
        points=[dict(id=str(i),ra_deg=150. if i<inside else 160.,dec_deg=0.,frame='ICRS') for i in range(total)])


@pytest.mark.parametrize('inside,total,outcome',[(4,7,'SATISFIED'),(3,7,'NOT_SATISFIED'),(2,4,'NOT_SATISFIED')])
def test_majority_and_independent_candidates(inside,total,outcome):
    r=assess_queue_rectangle_csv(source(),proposal(inside,total))
    assert len(r['candidates'])>=2
    assert len({c['candidate_id'] for c in r['candidates']})==len(r['candidates'])
    for c in r['candidates']:
        for v in c['position']['beam_variants']:
            assert v['outcome']==outcome
            assert v['coverage']['source_row_ids']==(c['geometry']['source_row_id'],)
            assert v['scientific_candidate_completeness']=='NOT_ESTABLISHED'
    assert r['duplication_status']=='NOT_EVALUATED'
    selected=assess_queue_rectangle_csv(source(),proposal(inside,total),candidate_id=r['candidates'][0]['candidate_id'])
    assert len(selected['candidates'])==1


def test_boundary_and_separate_array_results():
    radius=primary_beam_fwhm_deg(100,12)/2
    p=proposal(1,1)
    sky=SkyCoord(150*u.deg,0*u.deg).directional_offset_by(90*u.deg,radius*u.deg)
    p['points'][0].update(ra_deg=sky.ra.deg,dec_deg=sky.dec.deg)
    r=assess_queue_rectangle_csv(source(),p)
    variants={v['diameter_m']:v for v in r['candidates'][0]['position']['beam_variants']}
    assert variants[12.]['outcome']=='UNKNOWN'
    assert variants[7.]['outcome']=='SATISFIED'
    p['points'][0]['ra_deg']+=.001
    r=assess_queue_rectangle_csv(source(),p)
    assert [v['outcome'] for v in r['candidates'][0]['position']['beam_variants']]==['SATISFIED','NOT_SATISFIED']


def test_unresolved_geometry_frequency_and_invalid_selection(monkeypatch):
    r=assess_queue_rectangle_csv(source('galactic'),proposal(1,1))
    assert all(v['outcome']=='UNKNOWN' and v['coverage'] is None for c in r['candidates'] for v in c['position']['beam_variants'])
    monkeypatch.setattr('alma_duplicate.queue_rectangle_grid.candidate_frequency',lambda row:(None,'Ref.Frequency',('INVALID',)))
    r=assess_queue_rectangle_csv(source(),proposal(1,1))
    assert all(v['coverage'] is None for c in r['candidates'] for v in c['position']['beam_variants'])
    with pytest.raises(ValueError):
        assess_queue_rectangle_csv(source(),proposal(1,1),candidate_id='other-snapshot')


def test_budget_and_invalid_geometry(monkeypatch):
    monkeypatch.setattr('alma_duplicate.queue_rectangle_backend.MAX_TOTAL_PAIRS',1)
    with pytest.raises(ValueError,match='budget'):
        assess_queue_rectangle_csv(source(),proposal(1,7))
    parsed=source()
    parsed=replace(parsed,row_inputs=tuple(replace(r, spatial=replace(r.spatial,
        mosaic_spacing_arcsec=None)) if r.spatial.mosaic_raw=='Rectangle' else r for r in parsed.row_inputs))
    result=assess_queue_rectangle_csv(parsed,proposal(1,1))
    assert all(v['outcome']=='UNKNOWN' for c in result['candidates'] for v in c['position']['beam_variants'])
