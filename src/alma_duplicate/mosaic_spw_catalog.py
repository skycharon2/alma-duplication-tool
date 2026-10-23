"""Enumerate footprint-ready execution-local SPWs without spectral matching."""
import math
from alma_duplicate.archive_mosaic_footprint import circular_footprint


def build_spw_catalog(readiness, *, hpbw_coefficient, assume_uniform_field_antennas=False):
    if (isinstance(hpbw_coefficient, bool) or not math.isfinite(hpbw_coefficient)
            or hpbw_coefficient <= 0):
        raise ValueError("HPBW coefficient must be finite and positive")
    entries, executions = [], []
    seen = set()
    for execution in readiness['executions']:
        uid = execution['asdm_uid']
        if uid in seen:
            raise ValueError('Duplicate execution identity in readiness')
        seen.add(uid)
        spws = sorted({sid for f in execution['fields'] for scan in f['scans'] for sid in scan['spw_ids']})
        executions.append(dict(asdm_uid=uid, science_linked_spw_ids=spws,
            parse_errors=execution.get('parse_errors', {}), array_evidence=execution['array_evidence']))
        for sid in spws:
            row = dict(asdm_uid=uid, spw_id=sid, listobs_sha256=execution['listobs_sha256'])
            try:
                footprint = circular_footprint(readiness, asdm_uid=uid, spw_id=sid,
                    hpbw_coefficient=hpbw_coefficient, frequency_choice='reported-spw-centre',
                    assume_uniform_field_antennas=assume_uniform_field_antennas)
            except ValueError as exc:
                row.update(status='BLOCKED', reason=str(exc))
            else:
                row.update(status='AVAILABLE', frequency_hz=footprint['frequency_hz'],
                    frequency_frame=footprint['frequency_frame'], dish_diameter_m=footprint['dish_diameter_m'],
                    field_count=len(footprint['circles']), field_ids=[c['field_id'] for c in footprint['circles']],
                    excluded_field_ids=footprint['excluded_field_ids'],
                    half_power_radius_arcsec=footprint['half_power_radius_arcsec'])
            entries.append(row)
    return dict(schema_version='mosaic_spw_catalog_1', member_ous_uid=readiness['member_ous_uid'],
        source_name=readiness['source_name'], entries=entries, executions=executions,
        hpbw_coefficient=hpbw_coefficient, assume_uniform_field_antennas=assume_uniform_field_antennas,
        provenance=readiness['provenance'], inventory_scope='SUPPLIED_READINESS_EXECUTIONS_ONLY',
        completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', spectral_compatibility='NOT_EVALUATED',
        policy_status='NOT_EVALUATED')


def select_spws(catalog, selections):
    """Validate explicit pairs; emit the exact union CLI selection format."""
    if not isinstance(selections, list) or not 1 <= len(selections) <= 128:
        raise ValueError('Select between 1 and 128 execution/SPW pairs')
    available = {(e['asdm_uid'],e['spw_id']):e for e in catalog['entries']}
    seen, result, diameter = set(), [], None
    for item in selections:
        if not isinstance(item, dict) or set(item) != {'asdm_uid','spw_id'}:
            raise ValueError('Selection requires exactly asdm_uid and spw_id')
        uid, sid = item['asdm_uid'], item['spw_id']
        if not isinstance(uid,str) or type(sid) is not int:
            raise ValueError('Invalid selection identity')
        key = (uid,sid)
        if key in seen:
            raise ValueError('Duplicate selection')
        seen.add(key)
        row = available.get(key)
        if row is None or row['status'] != 'AVAILABLE':
            raise ValueError(f'Selected SPW unavailable: {uid} / {sid}')
        if diameter is not None and diameter != row['dish_diameter_m']:
            raise ValueError('Cross-array selection is not supported')
        diameter = row['dish_diameter_m']
        result.append(dict(asdm_uid=uid,spw_id=sid))
    return result
