import pytest
from alma_duplicate.mosaic_region_experiment import compare_region


def test_square_and_beam_have_both_disagreement_directions():
    result=compare_region('POLYGON ICRS 9.99 -0.01 10.01 -0.01 10.01 0.01 9.99 0.01',
        [dict(ra_deg=10,dec_deg=0,radius_arcsec=40)])
    assert result['counts']['BEAM_ONLY']>0
    assert result['counts']['REGION_ONLY']>0
    assert sum(result['counts'].values())==result['sample_count']
    assert result['policy_status']=='NOT_EVALUATED'


def test_wraparound_and_reversed_vertices_agree():
    circle=[dict(ra_deg=0,dec_deg=0,radius_arcsec=30)]
    a=compare_region('POLYGON ICRS 359.99 -0.01 0.01 -0.01 0.01 0.01 359.99 0.01',circle)
    b=compare_region('POLYGON ICRS 359.99 0.01 0.01 0.01 0.01 -0.01 359.99 -0.01',circle)
    assert a['counts']==b['counts']


@pytest.mark.parametrize('region', ['CIRCLE ICRS 0 0 1',
    'POLYGON ICRS 0 0 2 0 0 2','POLYGON ICRS 0 0 nan 0 0 1',
    'POLYGON ICRS 0 0 0.01 0.01 0 0.01 0.01 0'])
def test_unsupported_regions_fail(region):
    with pytest.raises(ValueError):compare_region(region,[dict(ra_deg=0,dec_deg=0,radius_arcsec=30)])
