"""Provisional Rectangle position-only adapter; never a duplication verdict."""
import math
from collections import Counter

from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.queue_mosaic import reconstruct_queue_mosaics
from alma_duplicate.queue_rectangle_grid import reconstruct_queue_rectangles
from alma_duplicate.rules.queue_mosaic_position import (
    QueueMosaicCoverage, _points, assess_queue_mosaic_position,
)

PROFILE = "QUEUE_RECTANGLE_MODEL_POSITION_1"
MAX_TOTAL_PAIRS = 1_000_000


def assess_queue_rectangle_csv(parsed, proposed, *, candidate_id=None,
                               boundary_epsilon_arcsec=0.001):
    """Evaluate independent array grids, conditional on the recorded model.

    Coverage association accepts the model's row/array binding only. Complete
    means all model grid points, never official candidate completeness.
    """
    if not isinstance(proposed, dict) or proposed.get('frame_basis') != 'USER_CONFIRMED_FIXED_ICRS':
        raise ValueError('Confirmed fixed ICRS proposal required')
    count = len(_points(proposed.get('points')))
    if (isinstance(boundary_epsilon_arcsec, bool) or
            not isinstance(boundary_epsilon_arcsec, (int, float)) or
            not math.isfinite(boundary_epsilon_arcsec) or not 0 <= boundary_epsilon_arcsec <= 1):
        raise ValueError('Numerical boundary tolerance must be between 0 and 1 arcsec')
    reconstruction = reconstruct_queue_mosaics(parsed)
    candidates = [c for c in reconstruction['candidates'] if c['geometry_kind'] == 'RECTANGLE'
                  and (candidate_id is None or c['candidate_id'] == candidate_id)]
    if candidate_id is not None and len(candidates) != 1:
        raise ValueError('Select a Rectangle candidate from this snapshot')
    grids = reconstruct_queue_rectangles(parsed)
    by_row = {c['source_row_id']: c for c in grids['candidates']}
    selected = [(c, by_row[c['source_rows'][0]['source_row_id']]) for c in candidates]
    if sum(a['pointing_count']*count for _, g in selected for a in g['arrays']) > MAX_TOTAL_PAIRS:
        raise ValueError('Rectangle batch pointing comparison budget exceeded')
    results = []
    for candidate, grid in selected:
        diameters = candidate['array_inference']['diameters_m']
        if list(diameters) != [a['diameter_m'] for a in grid['arrays']]:
            raise ValueError('Rectangle array binding mismatch')
        frequency = grid['frequency']['value_ghz']
        bindings, blockers = [], {}
        for array in grid['arrays']:
            d = array['diameter_m']
            reasons = list(array['reasons'])
            if frequency is None:
                reasons.append('CANDIDATE_FREQUENCY_UNRESOLVED')
            else:
                try:
                    width = primary_beam_fwhm_deg(frequency, d)
                    if width >= 180:
                        raise ValueError('Beam outside hemisphere')
                except ValueError:
                    reasons.append('CANDIDATE_BEAM_UNREPRESENTABLE')
            blockers[d] = reasons
            if reasons or array['geometry_status'] != 'GEOMETRY_RECONSTRUCTED':
                continue
            bindings.append(QueueMosaicCoverage(
                candidate['candidate_id'], reconstruction['snapshot_sha256'],
                (grid['source_row_id'],), d, frequency,
                f"{PROFILE}:{grid['frequency']['evidence']}", tuple(array['pointings']),
                f"{array['grid_method']}:{grid['source_row_id']}:{d}",
                association_confirmed=True, complete=array['model_grid_complete']))
        position = assess_queue_mosaic_position(proposed, reconstruction, candidate['candidate_id'],
            bindings, boundary_epsilon_arcsec=boundary_epsilon_arcsec)
        position.update(coverage_basis='PROVISIONAL_CSV_MODEL_BINDING',
            scientific_candidate_completeness='NOT_ESTABLISHED',
            outcome_scope='CONDITIONAL_ON_RECONSTRUCTED_MODEL')
        for variant in position['beam_variants']:
            bound = variant['coverage'] is not None
            variant.update(geometry_model_status='PROVISIONAL', array_basis='CSV_INFERRED',
                association_basis='ACCEPTED_MODEL_ROW_ARRAY_BINDING_NOT_OFFICIAL_VERIFICATION',
                coverage_scope='COMPLETE_FOR_RECONSTRUCTED_MODEL' if bound else 'NOT_ESTABLISHED',
                scientific_candidate_completeness='NOT_ESTABLISHED')
            variant['reasons'].extend(blockers[variant['diameter_m']])
        results.append(dict(candidate_id=candidate['candidate_id'], group=candidate['group'],
                            geometry=grid, position=position))
    outcomes = Counter(v['outcome'] for r in results for v in r['position']['beam_variants'])
    return dict(schema_version='queue_rectangle_csv_position_1', profile=PROFILE,
        model_status='PROVISIONAL', snapshot_sha256=reconstruction['snapshot_sha256'],
        source_url=reconstruction['source_url'], proposed=proposed, candidates=results,
        summary=dict(rectangle_candidates_evaluated=len(results),
                     position_outcomes={k: outcomes[k] for k in ('SATISFIED','NOT_SATISFIED','UNKNOWN')}),
        scientific_status='POSITION_ONLY', duplication_status='NOT_EVALUATED',
        candidate_union='NONE', array_aggregation='NONE',
        scientific_candidate_completeness='NOT_ESTABLISHED')
