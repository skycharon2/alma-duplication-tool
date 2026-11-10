"""Read-only projection: place saved Queue Mosaic matches in existing Explore rows.

No scientific evaluation, array selection, beam inference, or new source loads.
Every plotted beam comes from the already saved, bound Queue coverage evidence.
"""
from __future__ import annotations

from alma_duplicate.ui.queue_spectral_display import continuum_windows

from alma_duplicate.ui.report_view import (
    criterion_explanation,
    criterion_status,
    criterion_view,
)
from alma_duplicate.ui.visualization import spectral_view


def _criteria(records):
    result = []
    for record in records:
        if not isinstance(record, dict):
            continue
        view = criterion_view(record)
        result.append(dict(label=view['label'], proposed=view['proposed'],
                           candidate=view['candidate'], result=criterion_status(record),
                           reason=criterion_explanation(record)))
    return result


def _spectral(records, intent):
    """Use recorded Queue numerical comparisons; never infer a frequency interval."""
    result = spectral_view(records, intent)
    # These intervals are bound to this array branch's saved CONT-RMS evidence.
    # Do not reconstruct coverage from its representative frequency or total bandwidth.
    if intent == 'CONTINUUM' and result.get('available'):
        result['coverage'] = continuum_windows(records)
    return result if result.get('available') else dict(available=False,
        reason='This Queue branch has no independently displayable spectral operands.')


def merge_queue_matches(visual, queue_visual, *, details_url=None):
    """Append saved Queue array matches to this one original Explore batch.

    The Queue sidecar is already bounded to <=20 candidates by RunStore.
    Each complete matching array/intent is a separate selectable comparison.
    The legacy rows and their numerical evidence are left unchanged.
    """
    if queue_visual is None:
        return visual
    rows = list(visual['rows'])
    queue_count = 0
    for candidate in queue_visual['rows']:
        for branch_index, variant in enumerate(candidate.get('variants') or []):
            for intent_info in variant.get('science') or []:
                if intent_info.get('truth') != 'TRUE':
                    continue
                intent = intent_info.get('intent')
                if intent not in ('CONTINUUM', 'LINE'):
                    continue
                diameter = variant.get('diameter_m')
                geometry = variant['geometry']
                beams = geometry.get('points', []) if geometry.get('available') else []
                footprint = dict(available=bool(geometry.get('available')),
                    beams=beams, rectangle_reference=geometry.get('rectangle_reference'), geometry_type=f"QUEUE_{candidate['kind']}",
                    center=None, offset=None, outline=None,
                    radius_arcsec=geometry.get('radius_arcsec'),
                    diameter_m=diameter, frequency_ghz=geometry.get('frequency_ghz'),
                    separation_arcsec=None, model_status=candidate.get('model_status'),
                    point_count=geometry.get('point_count'),
                    covered_beam_count=sum(bool(b.get('covers_proposed')) for b in beams),
                    reason=(geometry.get('reason') or 'Queue geometry is model-conditional.'))
                records = variant.get('criterion_records') or []
                pairs = [pair for pair in (variant.get('line_pairs') or [])
                         if pair.get('truth') == 'TRUE']
                # A LINE branch can contain several matching SPW pairs. Retain
                # its count and link to the full report; never pretend the one
                # displayed pair represents the complete setup.
                displayed = pairs[0].get('criteria', []) if intent == 'LINE' and pairs else records
                identity = {'Project': candidate['project'], 'Target': candidate['target'],
                    'Member OUS': f"Queue {candidate['kind']} · {diameter:g}-m",
                    'Array': f'{diameter:g}-m',
                    'Queue candidate': candidate['id']}
                label = f"{candidate['target']} · {candidate['project']} · Queue {candidate['kind']} · {diameter:g}-m"
                record = dict(id=f"queue-{candidate['id']}-{branch_index}-{intent.lower()}",
                    anchor='queue-geometry-results', label=label, identity=identity,
                    source='QUEUE', intent=intent, spw='Mosaic', window=None,
                    beam_variant=None, array_diameter_m=diameter,
                    spatial=footprint, spectral=_spectral(displayed, intent),
                    criteria=_criteria(displayed), geometry_kind=candidate['kind'],
                    model_status=candidate.get('model_status'),
                    queue_line_matching_pairs=len(pairs),
                    details_url=details_url)
                queue_count += 1
                record['display_number'] = f"Q-{queue_visual['view']}-{queue_visual['page']}.{queue_count}"
                rows.append(record)
    visual['rows'] = rows
    visual['queue_comparison_count'] = queue_count
    visual['spatial_available'] = sum(bool(row['spatial'].get('available')) for row in rows)
    visual['spectral_available'] = sum(bool(row['spectral'].get('available')) for row in rows)
    visual['queue_page'] = queue_visual['page']
    visual['queue_pages'] = queue_visual['pages']
    visual['queue_view'] = queue_visual['view']
    visual['queue_visible_count'] = queue_visual['visible_count']
    return visual
