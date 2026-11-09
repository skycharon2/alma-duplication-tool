"""Charts preserve saved geometry, including wraparound and missing evidence."""
from copy import deepcopy
from hashlib import sha256

import pytest

from alma_duplicate.ui.mosaic_visualization import frequency_chart, position_chart, queue_rows
from tests.ui.test_queue_geometry_visualization import sample


def proposed():
    return dict(points=[dict(id='p1', frame='ICRS', ra_deg=0., dec_deg=0.),
                        dict(id='p2', frame='ICRS', ra_deg=359.999, dec_deg=0.)])


def test_archive_region_checksum_and_projection():
    raw = 'POLYGON ICRS 359.99 -0.01 0.01 -0.01 0.01 0.01 359.99 0.01'
    row = dict(source='Archive', footprint_evidence=dict(raw_s_region=raw, s_region_sha256=sha256(raw.encode()).hexdigest()))
    before = deepcopy(row)
    chart = position_chart(row, proposed())
    assert row == before
    assert chart['available'] and len(chart['outlines']) == 1
    assert chart['points'][1]['xy'][0] > chart['points'][0]['xy'][0]
    assert chart['scale_arcsec'] == pytest.approx(36, abs=.01)
    row['footprint_evidence']['s_region_sha256'] = 'incorrect'
    assert not position_chart(row, proposed())['available']


def test_queue_bound_beams_and_incomplete_grid():
    page = sample()
    chart = position_chart(next(queue_rows(page)), proposed())
    assert chart['available'] and len(chart['outlines']) == 2
    beam = page['document']['geometry_reports']['RECTANGLE']['candidates'][0]['position']['beam_variants'][0]
    beam['coverage']['complete'] = False
    assert not position_chart(next(queue_rows(page)), proposed())['available']
    beam['coverage']['complete'] = True
    beam['coverage']['candidate_id'] = 'foreign'
    assert not position_chart(next(queue_rows(page)), proposed())['available']


def test_invalid_proposal_and_opposite_hemisphere_are_not_plotted():
    row = next(queue_rows(sample()))
    points = proposed()
    points['points'][0]['frame'] = 'Galactic'
    assert not position_chart(row, points)['available']
    points['points'][0].update(frame='ICRS', ra_deg=180)
    assert not position_chart(row, points)['available']


def test_frequency_line_interval_and_identical_continuum_values():
    line = frequency_chart(dict(available=True, kind='interval', proposed=690, low=689, high=691))
    assert line['x'][1] < line['x'][0] < line['x'][2]
    cont = frequency_chart(dict(available=True, kind='representative', proposed=230, candidate=230))
    assert cont['x'][0] == cont['x'][1] == pytest.approx(350)
    assert frequency_chart(dict(available=False)) is None


def test_proposed_beams_use_proposal_array_and_requested_frequency():
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    row = next(queue_rows(sample()))  # Candidate is 12 m; proposal is 7 m.
    row['spectra'] = [dict(available=True, proposed=230.)]
    proposal = proposed()
    proposal['array'] = '7m'
    before = deepcopy(proposal)
    chart = position_chart(row, proposal)
    assert proposal == before
    assert chart['diameter'] == 7
    assert len(chart['proposal_beams'][0]['outlines']) == 2
    assert chart['proposal_beams'][0]['radius'] == pytest.approx(primary_beam_fwhm_deg(230., 7.)*1800)
    proposal.pop('array')
    missing = position_chart(row, proposal)
    assert missing['available'] and not missing['proposal_beams']
    assert 'array' in missing['beam_note']


def test_spectral_overview_uses_one_axis_and_keeps_pair_numbers():
    from alma_duplicate.ui.mosaic_visualization import spectral_overview
    spectra = [dict(available=True, kind='interval', proposed=230, low=229, high=231, spw='1'),
               dict(available=False),
               dict(available=True, kind='interval', proposed=230, low=228, high=232, spw='2')]
    overview = spectral_overview(spectra)
    first, second = overview['rows']
    assert [first['number'], second['number']] == [1, 3]
    assert first['proposed'] == second['proposed']
    assert second['low'] < first['low'] < first['high'] < second['high']
    assert spectral_overview([dict(available=False)]) is None
