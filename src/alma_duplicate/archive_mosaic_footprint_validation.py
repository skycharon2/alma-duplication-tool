"""Multi-SPW model diagnostics and explicitly limited Archive polygon probes."""
from collections import Counter
from hashlib import sha256
import math
import xml.etree.ElementTree as ET

from astropy.coordinates import SkyCoord
import astropy.units as u

from alma_duplicate.archive_mosaic_footprint import circular_footprint, probe_footprint
from alma_duplicate.archive_mosaic_pipeline import NS, read_mosaic_identity
from alma_duplicate.archive_mosaic_pointings import separation_arcsec


def region_vertices(raw, *, member, source, asdm):
    identity = read_mosaic_identity(raw)
    if (identity['member_ous_uid'], identity['target_name'], identity['asdm_uid']) != (member, source, asdm):
        raise ValueError('s_region TAP row differs from selected execution scope')
    table = ET.fromstring(raw).find('.//' + NS + 'TABLE')
    columns = table.findall(NS + 'FIELD')
    names = [f.get('name') for f in columns]
    row = dict(zip(names, [''.join(c.itertext()).strip() for c in table.find('.//' + NS + 'TR')]))
    text = row.get('s_region', '')
    parts = text.split()
    if len(parts) < 8 or [p.upper() for p in parts[:2]] != ['POLYGON', 'ICRS']:
        raise ValueError('Only a single ICRS STC-S polygon is supported')
    numbers = list(map(float, parts[2:]))
    if len(numbers) % 2 or len(numbers) > 20000:
        raise ValueError('Invalid or oversized polygon vertex list')
    vertices = []
    for index in range(0, len(numbers), 2):
        ra, dec = numbers[index:index + 2]
        if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValueError('Invalid s_region coordinate')
        vertices.append(dict(id=f'vertex-{index // 2}', frame='ICRS', ra_deg=ra, dec_deg=dec))
    return dict(vertices=vertices, raw_s_region=text, metadata_sha256=sha256(raw).hexdigest(),
        frequency_metadata=[dict(name=f.get('name'), unit=f.get('unit'), value=row[f.get('name')])
                            for f in columns if f.get('name') in ('frequency', 'em_min', 'em_max')],
        scope='SAMPLED_TAP_ROW_VERTICES_ONLY_NOT_REGION_EQUIVALENCE',
        frequency_relation='NOT_ESTABLISHED_WITH_SELECTED_LISTOBS_SPW')


def validate_footprints(readiness, *, asdm_uid, spw_ids, hpbw_coefficient,
                        frequency_choice, assume_uniform_field_antennas,
                        boundary_epsilon_arcsec, boundary_offset_arcsec, region_raw=None):
    if (not spw_ids or len(set(spw_ids)) != len(spw_ids) or len(spw_ids) > 32):
        raise ValueError('Select between one and 32 unique SPWs')
    if (not math.isfinite(boundary_epsilon_arcsec) or boundary_epsilon_arcsec <= 0
            or not math.isfinite(boundary_offset_arcsec) or boundary_offset_arcsec <= boundary_epsilon_arcsec):
        raise ValueError('Positive epsilon and a larger boundary offset are required')
    region = region_vertices(region_raw, member=readiness['member_ous_uid'], source=readiness['source_name'],
                             asdm=asdm_uid) if region_raw is not None else None
    runs = []
    for spw in sorted(spw_ids):
        footprint = circular_footprint(readiness, asdm_uid=asdm_uid, spw_id=spw,
            hpbw_coefficient=hpbw_coefficient, frequency_choice=frequency_choice,
            assume_uniform_field_antennas=assume_uniform_field_antennas)
        if boundary_offset_arcsec >= footprint['half_power_radius_arcsec']:
            raise ValueError('Boundary offset must be smaller than the beam radius')
        points, expected, origin_ids = [], {}, {}
        for circle in footprint['circles']:
            centre = SkyCoord(circle['ra_deg'] * u.deg, circle['dec_deg'] * u.deg, frame='icrs')
            point = dict(id=f"{circle['field_id']}-centre", frame='ICRS', ra_deg=circle['ra_deg'], dec_deg=circle['dec_deg'])
            points.append(point); expected[point['id']] = 'INSIDE'; origin_ids[point['id']] = circle['field_id']
            for bearing in (0, 90, 180, 270):
                for label, offset, status in (('inner', -boundary_offset_arcsec, 'INSIDE'),
                                               ('edge', 0, 'BOUNDARY'), ('outer', boundary_offset_arcsec, 'OUTSIDE')):
                    coord = centre.directional_offset_by(bearing * u.deg, (circle['radius_arcsec'] + offset) * u.arcsec)
                    point = dict(id=f"{circle['field_id']}-{bearing}-{label}", frame='ICRS',
                                 ra_deg=float(coord.ra.deg), dec_deg=float(coord.dec.deg))
                    points.append(point); expected[point['id']] = status; origin_ids[point['id']] = circle['field_id']
        results = probe_footprint(footprint, points, boundary_epsilon_arcsec=boundary_epsilon_arcsec)
        circles = {c['field_id']: c for c in footprint['circles']}
        failures = []
        for point in results['points']:
            origin = circles[origin_ids[point['id']]]
            delta = separation_arcsec(point, origin) - origin['radius_arcsec']
            actual = 'INSIDE' if delta < -boundary_epsilon_arcsec else 'BOUNDARY' if abs(delta) <= boundary_epsilon_arcsec else 'OUTSIDE'
            point.update(origin_field_id=origin['field_id'], expected_origin_status=expected[point['id']],
                         origin_status=actual, origin_boundary_distance_arcsec=delta)
            if actual != expected[point['id']]:
                failures.append(point['id'])
        run = dict(footprint=footprint, boundary_probes=results, origin_probe_failures=failures,
                   union_status_counts=dict(Counter(p['status'] for p in results['points'])))
        if region is not None:
            probes = probe_footprint(footprint, region['vertices'], boundary_epsilon_arcsec=boundary_epsilon_arcsec)
            for point in probes['points']:
                nearest = min(separation_arcsec(point, c) for c in footprint['circles'])
                point.update(nearest_field_separation_arcsec=nearest,
                             nearest_circle_boundary_delta_arcsec=nearest - footprint['half_power_radius_arcsec'])
            run['s_region_vertex_comparison'] = dict(probes=probes,
                status_counts=dict(Counter(p['status'] for p in probes['points'])),
                interpretation='GEOMETRY_DIFFERENCE_ONLY_NOT_HALF_POWER_GROUND_TRUTH')
        runs.append(run)
    products = [r['footprint']['frequency_hz'] * r['footprint']['half_power_radius_arcsec'] for r in runs]
    scaling = all(math.isclose(v, products[0], rel_tol=1e-12) for v in products)
    return dict(schema_version='archive_mosaic_footprint_validation_1', asdm_uid=asdm_uid,
        member_ous_uid=readiness['member_ous_uid'], source_name=readiness['source_name'], runs=runs,
        boundary_offset_arcsec=boundary_offset_arcsec, boundary_epsilon_arcsec=boundary_epsilon_arcsec,
        inverse_frequency_scaling_passed=scaling, s_region_evidence=region,
        status='DIAGNOSTIC_CHECKS_PASSED' if scaling and not any(r['origin_probe_failures'] for r in runs) else 'DIAGNOSTIC_CHECKS_FAILED',
        completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED')
