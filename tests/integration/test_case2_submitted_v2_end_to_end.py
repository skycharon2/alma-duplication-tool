"""CASE2 OT bytes through production discovery parser, metadata and V2 science."""
import json
from hashlib import sha256

import pytest

from scripts.accept_case2_mosaic_v2 import REQUEST, POINTINGS, run


@pytest.mark.parametrize('variant', ['original', 'frequency', 'rms', 'inventory'])
def test_case2_full_backend(tmp_path, variant):
    request = json.loads(REQUEST.read_text())['request']
    if variant == 'frequency':
        request['line_requirements'][0]['window_center']['value'] = 100
    elif variant == 'rms':
        request['line_requirements'][0]['rms']['value'] = .001
    elif variant == 'inventory':
        request['physical_spw_inventory_complete'] = True
    result, summary, fixture = run(tmp_path/'run', raw_request=request)
    assert set(fixture.fetched) == fixture.urls
    assert len(fixture.fetched) == 2  # Region query AND null-region fallback.
    assert len(fixture.queried) == 2
    assert summary['pointing_sha256'] == sha256(POINTINGS.read_bytes()).hexdigest()
    assert result['assessment_status'] == 'COMPLETED'
    assert summary['candidate_count'] == 2
    assert len(summary['contexts']) == 8
    assert all(c['inside'] == c['total'] == 3 for c in summary['contexts'])
    assert result['v2_science']['search_wide_duplication_verdict'] == 'NOT_EVALUATED'
    for candidate in result['candidates']:
        member = candidate['member_ous_uid'].split('/')[-1]
        recorded = fixture.metadata[member]
        assert candidate['metadata_rows'] == list(recorded.rows)
        for row, context in zip(recorded.rows, candidate['evaluation']['contexts'], strict=True):
            assert context['display_identity']['project'] == '2018.1.00294.S'
            assert context['display_identity']['target_name'] == 'NGC253'
            assert context['coverage']['raw_s_region'] == row['s_region']
            assert context['source_reference']['raw_row_id'].endswith(f":{recorded.rows.index(row):08d}")
            pair = context['line_pairs'][0]
            assert pair['attempt']['reference']['candidate_context_id'] == context['context_id']
            spw = row['obs_id'].split('.spw.')[-1]
            expected = 'TRUE' if member == 'X9c3' and spw == '25' and variant in {'original', 'inventory'} else 'FALSE'
            assert pair['truth'] == context['branches'][0]['truth'] == expected
            criteria = {c['criterion_id']: c['outcome'] for c in pair['criteria']}
            if spw != '25' or variant == 'frequency':
                assert criteria['LINE-COVERAGE'] == 'NOT_SATISFIED'
            if member == 'X9c5':
                assert criteria['ANGULAR'] == 'NOT_SATISFIED'
    # Read the persisted result twice: inspection is a pure local read.
    report_path = tmp_path/'run/assessment.json'
    assert json.loads(report_path.read_text()) == result
    assert json.loads(report_path.read_text()) == result
    assert len(fixture.queried) == 2


def test_offline_discovery_rejects_different_pointings(tmp_path):
    changed = tmp_path/'points.txt'
    changed.write_bytes(POINTINGS.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='bound to the original'):
        run(tmp_path/'run', pointings=changed)
    assert not (tmp_path/'run').exists()
