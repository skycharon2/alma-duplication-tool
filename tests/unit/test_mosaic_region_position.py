"""Spherical region containment and strict majority, independent of listobs."""
import json
from pathlib import Path

import pytest
from alma_duplicate.mosaic_region_position import assess_region_position
from alma_duplicate.proposed_mosaic import import_proposed


def proposal(coords):
    return dict(points=[dict(id=str(i),ra_deg=a,dec_deg=d) for i,(a,d) in enumerate(coords)],
                frame_basis='USER_CONFIRMED_FIXED_ICRS',completeness='USER_CONFIRMED_COMPLETE')


def run(coords, region='Circle ICRS 0 0 1'):
    return assess_region_position(proposal(coords), region, candidate_id='candidate-1')


@pytest.mark.parametrize('coords,outcome', [([(0,0),(.5,0),(2,0)],'SATISFIED'),
    ([(0,0),(.5,0),(2,0),(3,0)],'NOT_SATISFIED'), ([(0,0),(2,0),(3,0)],'NOT_SATISFIED'),
    ([(0,0),(1,0),(2,0)],'UNKNOWN'), ([(0,0),(.5,0),(1,0)],'SATISFIED'),
    ([(1,0),(2,0)],'NOT_SATISFIED')])
def test_strict_majority_and_boundary_bounds(coords,outcome):
    assert run(coords)['outcome'] == outcome


@pytest.mark.parametrize('region', [None,'','Polygon GALACTIC 0 0 1 0 0 1',
    'Union ICRS (Circle 0 0 1)', 'Circle ICRS 0 0 nan', 'Circle ICRS 0 0 -1',
    'Polygon ICRS 0 0 1 0', 'Polygon ICRS 0 0 2 2 0 2 2 0',
    'Polygon ICRS 0 0 1 0 2 0', 'Polygon ICRS 0 0 30 0 0 30',
    'Polygon ICRS 0 0 1 0 1 1 1 0 0 1'])
def test_invalid_or_unsupported_is_unknown(region):
    r = run([(0,0)],region)
    assert r['outcome'] == 'UNKNOWN' and r['unknown_count'] == 1 and r['reasons']


def test_wrap_reversal_and_closed_polygon():
    vertices = [(359,-1),(1,-1),(1,1),(359,1)]
    for v in (vertices,vertices[::-1],vertices+[vertices[0]]):
        text='Polygon ICRS '+' '.join(str(x) for p in v for x in p)
        r=run([(0,0),(360,0),(180,0),(359,-1)],text)
        assert [p['status'] for p in r['points']] == ['INSIDE','INSIDE','OUTSIDE','BOUNDARY']


def test_polar_polygon_and_circle():
    r=run([(0,90),(180,85)],'Polygon ICRS 0 89 120 89 240 89')
    assert [p['status'] for p in r['points']] == ['INSIDE','OUTSIDE']
    assert run([(150,90)],'Circle ICRS 0 90 .5')['outcome']=='SATISFIED'


def test_concave_polygon():
    r=run([(.5,.5),(1.5,1.5)],'Polygon ICRS 0 0 2 0 2 1 1 1 1 2 0 2')
    assert [p['status'] for p in r['points']]==['INSIDE','OUTSIDE']


def test_no_cross_candidate_pooling():
    coords=[(0,0),(3,0),(6,0)]
    assert all(run(coords,f'Circle ICRS {ra} 0 1')['outcome']=='NOT_SATISFIED' for ra in (0,3,6))


def test_proposal_validation():
    p=proposal([(0,0)])
    p['completeness']='NOT_CONFIRMED'
    assert assess_region_position(p,'Circle ICRS 0 0 1',candidate_id='x')['outcome']=='UNKNOWN'
    with pytest.raises(ValueError):run([(float('nan'),0)])
    with pytest.raises(ValueError):run([])


@pytest.mark.parametrize('member',['X9c3','X9c5'])
def test_real_case2_regions_with_ot_points(member):
    root=Path('tests/fixtures/archive/case2_mosaic_2026_10_26')
    p=import_proposed((root/'ot-12m.txt').read_bytes(),source_name='test',array='12m',
                      confirm_fixed_icrs=True,confirm_complete=True)
    rows=json.loads((root/member/'metadata.json').read_text())['rows']
    for i,row in enumerate(rows):
        r=assess_region_position(p,row['s_region'],candidate_id=f'{member}:{i}')
        assert r['inside_count']==3 and r['outcome']=='SATISFIED'


@pytest.mark.parametrize('fixture',['lmc_mosaic_2026_10_26','legacy_qa_text_2026_10_26'])
def test_other_captured_regions_parse_and_classify_vertices(fixture):
    rows=json.loads((Path('tests/fixtures/archive')/fixture/'metadata.json').read_text())['rows']
    for row in rows:
        tokens=row['s_region'].split()
        r=run([(float(tokens[2]),float(tokens[3]))],row['s_region'])
        assert r['points'][0]['status']=='BOUNDARY'


def test_circle_boundary_tolerance_against_astropy():
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    center=SkyCoord(359.99*u.deg,75*u.deg,frame='icrs')
    coords=[]
    for distance in (3599.99,3600,3600.01):
        p=center.directional_offset_by(45*u.deg,distance*u.arcsec)
        coords.append((p.ra.deg,p.dec.deg))
    assert [p['status'] for p in run(coords,'Circle ICRS 359.99 75 1')['points']] == ['INSIDE','BOUNDARY','OUTSIDE']


def test_high_latitude_edge_is_great_circle_not_constant_declination():
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    a=SkyCoord(10*u.deg,70*u.deg)
    b=SkyCoord(12*u.deg,70*u.deg)
    midpoint=a.directional_offset_by(a.position_angle(b),a.separation(b)/2)
    r=run([(midpoint.ra.deg,midpoint.dec.deg),(11,70)],'Polygon ICRS 10 70 12 70 12 71 10 71')
    assert [p['status'] for p in r['points']]==['BOUNDARY','OUTSIDE']


def test_invalid_ids_frame_and_limits():
    p=proposal([(0,0),(1,0)])
    p['points'][1]['id']='0'
    with pytest.raises(ValueError):assess_region_position(p,'Circle ICRS 0 0 1',candidate_id='x')
    p=proposal([(0,0)]);p['frame_basis']='UNKNOWN'
    assert assess_region_position(p,'Circle ICRS 0 0 1',candidate_id='x')['outcome']=='UNKNOWN'
    with pytest.raises(ValueError):assess_region_position(p,'Circle ICRS 0 0 1',candidate_id='x',boundary_arcsec=0)
