"""Explicit circular half-power union diagnostic, never a Mosaic policy decision."""
import math

from alma_duplicate.archive_mosaic_pointings import separation_arcsec

C_M_S = 299792458.0


def circular_footprint(readiness, *, asdm_uid, spw_id, hpbw_coefficient,
                       frequency_choice, assume_uniform_field_antennas=False):
    """Use one execution/SPW at its reported centre; preserve individual circles."""
    if (isinstance(hpbw_coefficient, bool) or not math.isfinite(hpbw_coefficient)
            or hpbw_coefficient <= 0):
        raise ValueError('Specify a finite positive HPBW coefficient')
    if frequency_choice != 'reported-spw-centre':
        raise ValueError('Explicit reported-spw-centre frequency choice required')
    if assume_uniform_field_antennas is not True:
        raise ValueError('Execution antenna table does not establish field participation; explicit assumption required')
    if type(spw_id) is not int or spw_id < 0:
        raise ValueError('Invalid execution-local SPW ID')
    matches = [e for e in readiness['executions'] if e['asdm_uid'] == asdm_uid]
    if len(matches) != 1:
        raise ValueError('Select exactly one verified execution')
    execution = matches[0]
    antenna = execution['antenna_evidence']
    if (execution['array_evidence']['status'] != 'BOUND' or antenna is None
            or antenna['diameters_m'] not in ([7.0], [12.0])):
        raise ValueError('Require a bound, single-diameter interferometric array')
    diameter = antenna['diameters_m'][0]
    circles, excluded, seen = [], [], set()
    frequency = None
    for field in execution['fields']:
        fid = field['field_id']
        if fid in seen:
            raise ValueError('Duplicate execution-local field identity')
        seen.add(fid)
        linked = [w for w in field['spectral_windows'] if w['spw_id'] == spw_id]
        if spw_id not in {sid for scan in field['scans'] for sid in scan['spw_ids']}:
            excluded.append(fid)
            continue
        if (field['asdm_uid'] != asdm_uid or field['input_status'] != 'EVIDENCE_BOUND'
                or len(linked) != 1 or spw_id not in field['explicit_full_res_spw_ids']):
            raise ValueError('Selected science FIELD/SPW inputs are not ready')
        window = linked[0]
        value = window['reported_centre_hz']
        if window['frame'] != 'TOPO' or not math.isfinite(value) or value <= 0:
            raise ValueError('Require a finite positive TOPO frequency')
        if frequency is not None and frequency != value:
            raise ValueError('Conflicting selected SPW centre frequency')
        frequency = value
        if (field['frame'] != 'ICRS' or not math.isfinite(field['ra_deg'])
                or not math.isfinite(field['dec_deg']) or not 0 <= field['ra_deg'] < 360
                or not -90 <= field['dec_deg'] <= 90):
            raise ValueError('Require valid ICRS coordinates')
        circles.append(dict(asdm_uid=asdm_uid, field_id=fid, frame='ICRS',
            ra_deg=field['ra_deg'], dec_deg=field['dec_deg'],
            ra_original=field['ra_original'], dec_original=field['dec_original'],
            scan_ids=[s['scan_id'] for s in field['scans'] if spw_id in s['spw_ids']]))
    if not circles:
        raise ValueError('No science fields reference the selected FULL_RES SPW')
    width_rad = hpbw_coefficient * C_M_S / frequency / diameter
    if not math.isfinite(width_rad) or not 0 < width_rad < math.pi:
        raise ValueError('Unsupported diagnostic beam width')
    radius = math.degrees(width_rad / 2) * 3600
    for circle in circles:
        circle['radius_arcsec'] = radius
    return dict(schema_version='archive_mosaic_footprint_diagnostic_1',
        member_ous_uid=readiness['member_ous_uid'], source_name=readiness['source_name'],
        asdm_uid=asdm_uid, spw_id=spw_id, model='CIRCULAR_HALF_POWER_DISK_UNION',
        response_threshold=0.5, hpbw_coefficient=hpbw_coefficient, dish_diameter_m=diameter,
        frequency_hz=frequency, frequency_frame='TOPO', frequency_choice=frequency_choice,
        hpbw_arcsec=2 * radius, half_power_radius_arcsec=radius,
        circles=circles, excluded_field_ids=excluded,
        array_evidence=execution['array_evidence'], listobs_sha256=execution['listobs_sha256'],
        provenance=readiness['provenance'], assumptions=[
            'CIRCULAR_SYMMETRIC_BEAMS', 'UNIFORM_EXECUTION_DISH_PARTICIPATION_FOR_SELECTED_FIELDS',
            'REPORTED_SPW_CENTRE_REPRESENTS_SELECTED_WINDOW', 'UNION_NOT_COMBINED_MOSAIC_SENSITIVITY'],
        boundary_rule='CLOSED_DISKS_WITH_EXPLICIT_PROBE_BOUNDARY_BAND',
        model_status='DIAGNOSTIC_ASSUMPTIONS_NOT_APPROVED_DUPLICATION_POLICY',
        coverage_area_status='NOT_COMPUTED', completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED',
        policy_status='NOT_EVALUATED')


def probe_footprint(footprint, points, *, boundary_epsilon_arcsec):
    """Classify diagnostic ICRS probes without counting proposed pointings or area."""
    if (isinstance(boundary_epsilon_arcsec, bool) or not math.isfinite(boundary_epsilon_arcsec)
            or boundary_epsilon_arcsec < 0):
        raise ValueError('Boundary epsilon must be finite and nonnegative')
    if len(points) * len(footprint['circles']) > 5_000_000:
        raise ValueError('Probe budget exceeded')
    ids, results = set(), []
    for point in points:
        if not isinstance(point['id'], str) or not point['id'] or point['id'] in ids:
            raise ValueError('Probe IDs must be nonempty and unique')
        ids.add(point['id'])
        if (point.get('frame') != 'ICRS' or not math.isfinite(point['ra_deg'])
                or not math.isfinite(point['dec_deg']) or not 0 <= point['ra_deg'] < 360
                or not -90 <= point['dec_deg'] <= 90):
            raise ValueError('Invalid ICRS probe coordinate')
        inside, boundary = [], []
        for circle in footprint['circles']:
            delta = separation_arcsec(point, circle) - circle['radius_arcsec']
            if delta < -boundary_epsilon_arcsec:
                inside.append(circle['field_id'])
            elif abs(delta) <= boundary_epsilon_arcsec:
                boundary.append(circle['field_id'])
        results.append(dict(**point, status='INSIDE' if inside else 'BOUNDARY' if boundary else 'OUTSIDE',
                            inside_field_ids=inside, boundary_field_ids=boundary))
    return dict(boundary_epsilon_arcsec=boundary_epsilon_arcsec,
                epsilon_scope='NUMERICAL_CLASSIFICATION_BAND_NOT_ASTROMETRIC_UNCERTAINTY', points=results)
