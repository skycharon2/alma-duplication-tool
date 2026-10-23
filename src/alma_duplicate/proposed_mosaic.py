"""Bind OT pointings to a proposed observation and assess selected Archive coverage."""
from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
from alma_duplicate.archive_mosaic_footprint import circular_footprint, probe_footprint
from alma_duplicate.archive_mosaic_pointings import separation_arcsec


def import_proposed(raw, *, source_name, array, confirm_fixed_icrs=False, confirm_complete=False):
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError('Proposed source name required')
    if array not in ('7m', '12m'):
        raise ValueError('Explicit proposed array must be 7m or 12m')
    if confirm_fixed_icrs is not True:
        raise ValueError('Confirm fixed ICRS pointings; moving targets are not supported')
    report = parse_ot_pointings(raw)
    report.update(source_name=source_name.strip(), array=array,
                  binding_basis='USER_SUPPLIED_NOT_ENCODED_IN_OT_FILE',
                  frame_basis='USER_CONFIRMED_FIXED_ICRS',
                  completeness='USER_CONFIRMED_COMPLETE' if confirm_complete is True else 'NOT_CONFIRMED')
    return report


def assess_proposed(proposed, readiness, *, asdm_uid, spw_id, hpbw_coefficient,
                    boundary_epsilon_arcsec, assume_uniform_field_antennas=False):
    """Evaluate one selected execution/SPW; do not infer spectral compatibility."""
    footprint = circular_footprint(readiness, asdm_uid=asdm_uid, spw_id=spw_id,
        hpbw_coefficient=hpbw_coefficient, frequency_choice='reported-spw-centre',
        assume_uniform_field_antennas=assume_uniform_field_antennas)
    if proposed['array'] != f"{int(footprint['dish_diameter_m'])}m":
        raise ValueError('Cross-array comparison is not supported in this interface')
    probes = probe_footprint(footprint, proposed['points'], boundary_epsilon_arcsec=boundary_epsilon_arcsec)
    for point in probes['points']:
        point['circle_relations'] = []
        for circle in footprint['circles']:
            distance = separation_arcsec(point, circle)
            point['circle_relations'].append(dict(field_id=circle['field_id'],
                separation_arcsec=distance, radius_arcsec=circle['radius_arcsec'],
                boundary_delta_arcsec=distance-circle['radius_arcsec']))
    counts = {s: sum(p['status'] == s for p in probes['points']) for s in ('INSIDE', 'BOUNDARY', 'OUTSIDE')}
    total = len(probes['points'])
    if not total:
        raise ValueError('No proposed pointings')
    lower, upper = counts['INSIDE'], counts['INSIDE'] + counts['BOUNDARY']
    spatial = ('MET' if 2 * lower > total else
               'NOT_MET' if 2 * upper <= total else 'BOUNDARY_UNRESOLVED')
    if proposed['completeness'] != 'USER_CONFIRMED_COMPLETE':
        spatial = 'PROPOSED_COMPLETENESS_UNCONFIRMED'
    return dict(schema_version='proposed_mosaic_spatial_1', proposed=proposed, footprint=footprint,
        probe_results=probes, pointing_count=total, status_counts=counts,
        covered_fraction_lower=lower/total, covered_fraction_upper=upper/total,
        spatial_condition=spatial, threshold='STRICTLY_MORE_THAN_HALF',
        assessment_scope='SUPPLIED_PROPOSED_LIST_VS_SELECTED_ARCHIVE_EXECUTION_SPW',
        coverage_model_acceptance='PROJECT_SUPERVISOR_CONFIRMATION_REPORTED_2026_10_23',
        archive_completeness=footprint['completeness'],
        spectral_compatibility='NOT_EVALUATED', policy_status='NOT_EVALUATED')
