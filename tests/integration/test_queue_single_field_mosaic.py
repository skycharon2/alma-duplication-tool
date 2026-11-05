from dataclasses import replace

import pytest

from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.queue_single_field_mosaic import assess_single_field_science
from tests.integration.test_queue_custom_science import candidate, request, pointings, line_request


def evaluate(changes=None, ras=(0.001,), req=None, copies=1):
    req = req or request()[0]
    parsed = candidate({'Mosaic': '', 'Long Offset': '0', 'Lat Offset': '0',
                        'RA': '359.999', 'Dec': '60', **(changes or {})}, rows=copies)
    p = pointings(req)
    p['points'] = [dict(id=str(i), ra_deg=ra, dec_deg=60, frame='ICRS') for i, ra in enumerate(ras)]
    return assess_single_field_science(parsed, req, p)['candidates'][0]


@pytest.mark.parametrize('inside,total,outcome', [(1,2,'NOT_SATISFIED'), (2,3,'SATISFIED'),
    (1,3,'NOT_SATISFIED'), (0,2,'NOT_SATISFIED')])
def test_spherical_majority(inside,total,outcome):
    c = evaluate(ras=(0.001,)*inside + (1.,)*(total-inside))
    for v in c['position']['beam_variants']:
        assert v['covered_count_lower'] == inside
        assert v['outcome'] == outcome


def test_independent_arrays_and_duplicate_row_binding():
    delta_ra = (primary_beam_fwhm_deg(230,7) + primary_beam_fwhm_deg(230,12))/2
    c = evaluate(ras=((359.999 + delta_ra)%360,), copies=2)
    assert len(c['source_rows']) == 2
    assert c['science']['matching_arrays_by_intent']['CONTINUUM'] == [7.]


def test_unknown_position_and_unrelated_negative_frequency():
    c = evaluate({'Mos. Coord.': 'galactic'})
    assert c['science']['branches'][0]['truth'] == 'UNKNOWN'
    c = evaluate({'Ref.Frequency': '1e-8'})
    assert all(v['outcome'] == 'UNKNOWN' for v in c['position']['beam_variants'])
    c = evaluate({'Ref.Frequency': '100'})
    assert all(v['outcome'] == 'SATISFIED' for v in c['position']['beam_variants'])
    assert c['science']['branches'][0]['truth'] == 'FALSE'


def test_single_field_line_pairs_share_row_and_array():
    req = replace(line_request(center_ghz=226., resolution_kms=20), geometry='MOSAIC')
    c = evaluate({'Project Code': '2024.1.00001.S', 'Polarization': 'DOUBLE',
                  'Req.Sensitivity': '0.001', 'Spec.Res. SPW 1': '0.9765625'}, req=req)
    assert c['science']['matching_arrays_by_intent']['LINE'] == [7., 12.]
    for v in c['science']['variants']:
        assert all(p['reference']['source_row_id'] == c['geometry']['source_row_id']
                   for p in v['line_pairs'])


def test_single_field_batch_budget_counts_distinct_candidates_and_arrays(monkeypatch):
    from unittest.mock import Mock
    from alma_duplicate import queue_single_field_mosaic as adapter
    from tests.integration.test_candidate_search import queue_rows

    rows = []
    for name in ('One', 'Two'):
        row = candidate({'Mosaic': '', 'Target Name': name}, rows=1).row_inputs[0]
        rows.append(dict(zip(row.raw_row.declared_columns, row.raw_row.raw_values)))
    parsed = queue_rows(*rows, rows[0])
    req = request()[0]
    proposed = pointings(req)
    limit = 4 * len(proposed['points'])  # Two distinct candidates, each with two arrays.
    monkeypatch.setattr(adapter, 'MAX_PAIRS', limit)
    assert len(assess_single_field_science(parsed, req, proposed)['candidates']) == 2
    monkeypatch.setattr(adapter, 'MAX_PAIRS', limit - 1)
    position = Mock()
    monkeypatch.setattr(adapter, 'assess_queue_mosaic_position', position)
    with pytest.raises(ValueError, match='Single Field batch pointing comparison budget exceeded'):
        assess_single_field_science(parsed, req, proposed)
    position.assert_not_called()
