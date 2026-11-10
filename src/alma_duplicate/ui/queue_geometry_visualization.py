"""Bounded, read-only Queue Custom/Rectangle footprint projection for Explore.

Only the saved candidate/array coverage binding may supply positions and radii.
This module neither reconstructs pointings nor evaluates scientific conditions.
"""

from __future__ import annotations

import math
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.ui.queue_browser import presentation
from alma_duplicate.ui.visualization import beam_outline, number, position, sky_offset

# Avoid silently truncating a footprint: an oversized array is not plotted.
MAX_ARRAY_BEAMS = 240
MAX_PAGE_BEAMS = 800


def _array_science(candidate, diameter):
    science = candidate.get('science') or {}
    variants = [v for v in science.get('variants', [])
                if v.get('diameter_m') == diameter]
    if len(variants) != 1:
        return []
    return [dict(intent=b.get('branch'), result=b.get('status'), truth=b.get('truth'))
            for b in variants[0].get('branches', [])]


def _matched_ids(variant):
    """Position evidence only; does not infer matches from chart geometry."""
    seen = set()
    for probe in variant.get('points') or []:
        for pid in probe.get('matched_point_ids') or []:
            if isinstance(pid, str):
                seen.add(pid)
    return seen


def _footprint(variant, origin, remaining, candidate_id, snapshot_sha256, source_ids):
    """Return a complete plotted array or an explicit display limitation."""
    missing = dict(available=False, points=[], reason='Saved array coverage is unavailable.')
    coverage = variant.get('coverage')
    if not isinstance(coverage, dict):
        return missing, 0
    if (coverage.get('candidate_id') != candidate_id
            or coverage.get('snapshot_sha256') != snapshot_sha256
            or coverage.get('source_row_ids') != source_ids):
        return dict(missing, reason='Saved coverage is not bound to this candidate or snapshot.'), 0
    if coverage.get('association_confirmed') is not True or coverage.get('complete') is not True:
        return dict(missing, reason='Coverage binding or model grid is incomplete.'), 0
    diameter = variant.get('diameter_m')
    radius = variant.get('radius_arcsec')
    if (diameter not in (7.0, 12.0) or not number(radius)
            or not 0 < radius < 90*3600 or not number(coverage.get('frequency_ghz'))
            or coverage.get('diameter_m') != diameter):
        return dict(missing, reason='Saved array-specific radius or frequency is invalid.'), 0
    centers = coverage.get('points')
    if not isinstance(centers, list) or not centers:
        return dict(missing, reason='No saved candidate pointings.'), 0
    if len(centers) > MAX_ARRAY_BEAMS or len(centers) > remaining:
        return dict(missing, reason='Footprint exceeds bounded display budget; use full report download.',
                    point_count=len(centers)), 0
    matched = _matched_ids(variant)
    plotted, ids = [], set()
    for item in centers:
        if not isinstance(item, dict) or item.get('frame') != 'ICRS':
            return dict(missing, reason='A saved pointing has an unresolved coordinate frame.'), 0
        point_id = item.get('id')
        center = position(item)
        if not isinstance(point_id, str) or not point_id or point_id in ids or center is None:
            return dict(missing, reason='Saved pointing identity or coordinates are invalid.'), 0
        ids.add(point_id)
        offset = sky_offset(origin, center)
        outline = beam_outline(origin, center, radius/3600)
        if offset is None or outline is None:
            return dict(missing, reason='A beam lies outside the display projection hemisphere.'), 0
        plotted.append(dict(id=point_id, center=list(center), offset=offset, outline=outline,
                            covers_proposed=point_id in matched))
    return dict(available=True, points=plotted, point_count=len(plotted),
                radius_arcsec=radius, frequency_ghz=coverage['frequency_ghz'],
                reason='', model_complete=True), len(plotted)


def _rectangle_reference(candidate, origin):
    """Display the saved input rectangle; never treat it as evaluated coverage."""
    grid = candidate.get('geometry') or {}
    g = grid.get('input_geometry') or {}
    keys = ('ra_deg', 'dec_deg', 'longitude_offset_arcsec', 'latitude_offset_arcsec',
            'length_arcsec', 'width_arcsec', 'pa_deg')
    if g.get('frame', '').lower() != 'icrs' or not all(number(g.get(k)) for k in keys):
        return None
    if (not 0 <= g['ra_deg'] < 360 or not -90 < g['dec_deg'] < 90
            or min(g['length_arcsec'], g['width_arcsec']) <= 0
            or math.hypot(g['length_arcsec'], g['width_arcsec'])/2
            + math.hypot(g['longitude_offset_arcsec'], g['latitude_offset_arcsec']) >= 90*3600):
        return None
    def move(point, east, north):
        return point.directional_offset_by(math.atan2(east, north)*u.rad,
                                           math.hypot(east, north)*u.arcsec)
    centre = move(SkyCoord(g['ra_deg']*u.deg, g['dec_deg']*u.deg),
                  g['longitude_offset_arcsec'], g['latitude_offset_arcsec'])
    angle = math.radians(g['pa_deg'])
    corners = [(-1,-1), (1,-1), (1,1), (-1,1), (-1,-1)]
    sky = []
    # Sample sides to preserve the same spherical offset convention as the grid.
    for start, end in zip(corners, corners[1:]):
        for i in range(12):
            t = i/12
            p = (start[0]*(1-t)+end[0]*t)*g['length_arcsec']/2
            q = (start[1]*(1-t)+end[1]*t)*g['width_arcsec']/2
            point = move(centre, p*math.cos(angle)+q*math.sin(angle),
                         -p*math.sin(angle)+q*math.cos(angle))
            sky.append([float(point.ra.deg), float(point.dec.deg)])
    sky.append(sky[0])
    outline = [sky_offset(origin, point) for point in sky]
    if any(point is None for point in outline):
        return None
    return dict(sky_outline=sky, outline=outline,
                label='Input rectangle · reference only, not beam coverage')


def queue_geometry_visualization_data(queue_page, origin):
    """Project ONLY candidates read through RunStore.queue_page()'s JSONL index.

    A page includes <=20 candidates. The caller supplies the proposed ICRS
    coordinate extracted from the saved baseline report, never browser input.
    """
    if queue_page is None:
        return None
    saved = queue_page.get('document') or {}
    source = (saved.get('sources') or {}).get('QUEUE') or {}
    rows = []
    total_beams = 0
    valid_origin = (isinstance(origin, (tuple, list)) and len(origin) == 2
                    and number(origin[0]) and number(origin[1])
                    and 0 <= origin[0] < 360 and -90 <= origin[1] <= 90)
    for entry in presentation(saved):
        candidate = entry['candidate']
        kind = entry['kind']
        if kind not in ('CUSTOM', 'RECTANGLE'):
            continue
        science = candidate.get('science') or {}
        position_report = candidate.get('position') or {}
        variants = []
        for variant in position_report.get('beam_variants') or []:
            diameter = variant.get('diameter_m')
            if not valid_origin:
                geometry = dict(available=False, points=[], reason='Proposed ICRS position is unavailable.')
                used = 0
            else:
                geometry, used = _footprint(variant, origin, MAX_PAGE_BEAMS-total_beams,
                                        candidate.get('candidate_id'),
                                        position_report.get('snapshot_sha256'),
                                        position_report.get('source_row_ids'))
            if kind == 'RECTANGLE' and geometry.get('available'):
                geometry['rectangle_reference'] = _rectangle_reference(candidate, origin)
            total_beams += used
            records = [v for v in science.get('variants', []) if v.get('diameter_m') == diameter]
            selected_science = records[0] if len(records) == 1 else {}
            variants.append(dict(diameter_m=diameter, position_outcome=variant.get('outcome'),
                                 position_reasons=variant.get('reasons') or [],
                                 science=_array_science(candidate, diameter),
                                 criterion_records=selected_science.get('criteria') or [],
                                 line_pairs=selected_science.get('line_pairs') or [],
                                 geometry=geometry))
        group = candidate.get('group') or {}
        rows.append(dict(id=candidate.get('candidate_id'), kind=kind,
                         project=group.get('project_code') or 'Not recorded',
                         target=group.get('target_name') or 'Queue candidate',
                         model_status=science.get('model_status') or 'PROVISIONAL',
                         candidate_completeness=science.get('scientific_candidate_completeness') or 'NOT_ESTABLISHED',
                         snapshot_sha256=position_report.get('snapshot_sha256'),
                         source_row_count=len(position_report.get('source_row_ids') or []),
                         overall_science=[dict(intent=b.get('branch'), result=b.get('status'), truth=b.get('truth'))
                                          for b in science.get('branches') or []],
                         variants=variants))
    return dict(rows=rows, page=queue_page['page'], pages=queue_page['pages'],
                view=queue_page['result_view'], visible_count=queue_page['visible_count'],
                source_status=source.get('status') or 'UNKNOWN',
                origin=list(origin) if valid_origin else None,
                display_beams=total_beams, model_note='Array-inferred, model-conditional Queue geometry; display only.')
