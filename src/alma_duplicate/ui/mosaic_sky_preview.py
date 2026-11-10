"""Read-only sky scene from bound Mosaic Explorer evidence.

Only the submitted ICRS pointings and validated, saved candidate geometry may
appear.  Never promote a display outline into a matching/duplication decision.
"""
from alma_duplicate.ui.queue_geometry_visualization import _footprint
from alma_duplicate.ui.region_display import saved_region_outline
from alma_duplicate.ui.visualization import number, position

MAX_PROPOSAL_POINTS = 2000
MAX_REGION_VERTICES = 4096


def _proposal_points(proposed):
    raw = proposed.get('points') or []
    if not isinstance(raw, list) or not 0 < len(raw) <= MAX_PROPOSAL_POINTS:
        return None
    points = []
    ids = set()
    for point in raw:
        if not isinstance(point, dict) or point.get('frame') != 'ICRS':
            return None
        identity = point.get('id')
        coordinates = position(point)
        if not isinstance(identity, str) or not identity or identity in ids or coordinates is None:
            return None
        ids.add(identity)
        points.append(dict(id=identity, center=list(coordinates)))
    return points


def sky_preview(row, proposed, chart):
    """Produce bounded presentation-only sky data aligned with Position charts.

    The Position chart supplies the same conservative availability gate.  Sky
    coordinates are derived from the *saved* source objects, never SVG pixels.
    """
    points = _proposal_points(proposed)
    unavailable = dict(available=False, proposed=[], proposed_beams=[], candidate=None,
                       reason='Submitted ICRS pointings are unavailable or invalid.')
    if points is None:
        return unavailable
    scene = dict(available=True, proposed=points, proposed_beams=[], candidate=None,
                 reason='', source=row.get('source'), project=row.get('project'),
                 label=row.get('target') or row.get('candidate'),
                 context_id=row.get('context_id'))
    if not isinstance(chart, dict) or not chart.get('available'):
        scene['reason'] = (chart or {}).get('reason') or 'Bound candidate geometry unavailable.'
        return scene
    # The chart already bounds and validates every proposed beam model.  Only
    # radii are transferred; individual sky centres remain the uploaded points.
    for beam in chart.get('proposal_beams') or []:
        frequency, radius = beam.get('frequency'), beam.get('radius')
        if number(frequency) and number(radius) and frequency > 0 and 0 < radius < 324000:
            scene['proposed_beams'].append(dict(frequency_ghz=frequency, radius_arcsec=radius))
    evidence = row.get('footprint_evidence') or {}
    if row.get('source') == 'Archive' and evidence.get('raw_s_region'):
        try:
            _, outline = saved_region_outline(evidence)
        except (TypeError, ValueError):
            scene['reason'] = 'Saved Archive s_region failed validation.'
            return scene
        if not outline or len(outline) > MAX_REGION_VERTICES:
            scene['reason'] = 'Saved Archive s_region exceeds the sky-display budget.'
            return scene
        scene['candidate'] = dict(kind='region', outline=outline,
                                  provenance='Saved Archive s_region; checksum verified')
    elif row.get('source') == 'Queue':
        footprint, _ = _footprint(evidence.get('variant') or {}, chart['origin'],
                                 240, row.get('candidate'), evidence.get('snapshot'),
                                 evidence.get('source_ids'))
        if not footprint['available']:
            scene['reason'] = footprint.get('reason') or 'Queue coverage unavailable.'
            return scene
        scene['candidate'] = dict(kind='beams', radius_arcsec=footprint['radius_arcsec'],
                                  beams=[dict(id=p['id'], center=p['center']) for p in footprint['points']],
                                  provenance='Bound saved Queue array beam union')
    elif row.get('source') == 'Archive' and row.get('beams'):
        candidate_beams = []
        for beam in row['beams']:
            center = position(beam)
            radius = beam.get('radius_arcsec')
            if beam.get('frame') != 'ICRS' or center is None or not number(radius) or not 0 < radius < 324000:
                scene['reason'] = 'Archive beam metadata invalid.'
                return scene
            candidate_beams.append(dict(center=list(center), radius_arcsec=radius))
        scene['candidate'] = dict(kind='beams', radius_arcsec=row['beams'][0]['radius_arcsec'],
                                  beams=candidate_beams, provenance='Saved Archive beam evidence')
    else:
        scene['reason'] = 'No verified saved candidate footprint.'
    return scene
