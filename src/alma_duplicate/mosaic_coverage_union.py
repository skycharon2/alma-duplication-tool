"""Explicit execution/SPW union for one verified Archive Member and target."""
import math
from alma_duplicate.archive_mosaic_footprint import circular_footprint
from alma_duplicate.archive_mosaic_pointings import separation_arcsec


def assess_union(proposed, readiness, *, selections, hpbw_coefficient,
                 boundary_epsilon_arcsec, assume_uniform_field_antennas=False):
    """Combine selected disks without inferring frequency or Member completeness."""
    if not isinstance(selections, list) or not 1 <= len(selections) <= 128:
        raise ValueError('Select between 1 and 128 execution/SPW pairs')
    if (isinstance(boundary_epsilon_arcsec, bool) or not math.isfinite(boundary_epsilon_arcsec)
            or boundary_epsilon_arcsec < 0):
        raise ValueError('Boundary epsilon must be finite and nonnegative')
    pairs, footprints, circles = set(), [], []
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != {'asdm_uid', 'spw_id'}:
            raise ValueError('Each selection requires exactly asdm_uid and spw_id')
        uid, spw = selection['asdm_uid'], selection['spw_id']
        if not isinstance(uid, str) or not uid or type(spw) is not int or spw < 0:
            raise ValueError('Invalid execution/SPW selection')
        if (uid, spw) in pairs:
            raise ValueError('Duplicate execution/SPW selection')
        pairs.add((uid, spw))
        footprint = circular_footprint(readiness, asdm_uid=uid, spw_id=spw,
            hpbw_coefficient=hpbw_coefficient, frequency_choice='reported-spw-centre',
            assume_uniform_field_antennas=assume_uniform_field_antennas)
        if proposed['array'] != f"{int(footprint['dish_diameter_m'])}m":
            raise ValueError('Cross-array union is not supported')
        footprints.append(footprint)
        circles.extend(dict(c, spw_id=spw, frequency_hz=footprint['frequency_hz'],
                            dish_diameter_m=footprint['dish_diameter_m']) for c in footprint['circles'])
    points = proposed['points']
    if not points or len(points)*len(circles) > 5_000_000:
        raise ValueError('Empty proposed list or comparison budget exceeded')
    ids, results = set(), []
    counts = dict(INSIDE=0, BOUNDARY=0, OUTSIDE=0)
    for point in points:
        if not isinstance(point['id'], str) or not point['id'] or point['id'] in ids:
            raise ValueError('Proposed row IDs must be unique and nonempty')
        ids.add(point['id'])
        if (point.get('frame') != 'ICRS' or not math.isfinite(point['ra_deg'])
                or not math.isfinite(point['dec_deg']) or not 0 <= point['ra_deg'] < 360
                or not -90 <= point['dec_deg'] <= 90):
            raise ValueError('Invalid ICRS proposed coordinate')
        relations, inside, boundary = [], [], []
        for circle in circles:
            identity = {k: circle[k] for k in ('asdm_uid', 'spw_id', 'field_id')}
            distance = separation_arcsec(point, circle)
            delta = distance-circle['radius_arcsec']
            status = ('INSIDE' if delta < -boundary_epsilon_arcsec else
                      'BOUNDARY' if abs(delta) <= boundary_epsilon_arcsec else 'OUTSIDE')
            if status == 'INSIDE': inside.append(identity)
            if status == 'BOUNDARY': boundary.append(identity)
            relations.append(dict(**identity, separation_arcsec=distance,
                radius_arcsec=circle['radius_arcsec'], boundary_delta_arcsec=delta, status=status))
        status = 'INSIDE' if inside else 'BOUNDARY' if boundary else 'OUTSIDE'
        counts[status] += 1
        results.append(dict(**point, status=status, inside_circles=inside,
                            boundary_circles=boundary, circle_relations=relations))
    total = len(points)
    lower, upper = counts['INSIDE'], counts['INSIDE']+counts['BOUNDARY']
    spatial = 'MET' if lower*2 > total else 'NOT_MET' if upper*2 <= total else 'BOUNDARY_UNRESOLVED'
    if proposed['completeness'] != 'USER_CONFIRMED_COMPLETE':
        spatial = 'PROPOSED_COMPLETENESS_UNCONFIRMED'
    selected_uids = {uid for uid, _ in pairs}
    return dict(schema_version='proposed_mosaic_union_1', proposed=proposed,
        member_ous_uid=readiness['member_ous_uid'], archive_source_name=readiness['source_name'],
        selections=selections, footprints=footprints, circles=circles,
        unselected_asdm_uids=sorted({e['asdm_uid'] for e in readiness['executions']}-selected_uids),
        execution_inventory_scope='READINESS_INPUT_ONLY_NOT_COMPLETE_MEMBER_INVENTORY',
        selected_input_status='ALL_SELECTED_INPUTS_VALIDATED',
        selection_basis='CALLER_SELECTED_NOT_AUTOMATIC_SPECTRAL_MATCH',
        probe_results=dict(points=results, boundary_epsilon_arcsec=boundary_epsilon_arcsec,
            epsilon_scope='NUMERICAL_CLASSIFICATION_BAND_NOT_ASTROMETRIC_UNCERTAINTY'),
        pointing_count=total, circle_count=len(circles), status_counts=counts,
        covered_fraction_lower=lower/total, covered_fraction_upper=upper/total,
        spatial_condition=spatial, threshold='STRICTLY_MORE_THAN_HALF',
        assessment_scope='SUPPLIED_PROPOSED_LIST_VS_SELECTED_ARCHIVE_EXECUTION_SPW_UNION',
        coverage_model_acceptance='PROJECT_SUPERVISOR_CONFIRMATION_REPORTED_2026_10_23',
        archive_completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED',
        spectral_compatibility='NOT_EVALUATED', policy_status='NOT_EVALUATED')
