"""Bind field spectral links and dish evidence; do not calculate primary-beam coverage."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from alma_duplicate.archive_array_evidence import COMPONENTS, load_archive_array_catalog
from alma_duplicate.archive_mosaic_pointings import load_package_executions
from alma_duplicate.parsers.archive_listobs_setup import parse_spectral_windows, parse_antennas


def bind_array(catalog, *, member, source, antennas):
    result = dict(status='UNKNOWN', components=[], source_records=[], reasons=[],
                  scope='AQ_MEMBER_TARGET_LABEL_WITH_EXECUTION_DISH_CROSSCHECK')
    if catalog is None:
        result['reasons'] = ['AQ_ARRAY_EVIDENCE_MISSING']
        return result
    source_id = f'{member}.source.{source}'
    records = [r for r in catalog.records if r.observation_id == source_id]
    result['source_records'] = [asdict(r) for r in records]
    result['catalog_manifest_sha256'] = catalog.manifest_sha256
    if len(records) != 1:
        result['reasons'] = ['AQ_SOURCE_MISSING_OR_AMBIGUOUS']
        return result
    record = records[0]
    if record.member_ous_uid != member or record.source_name != source:
        result['reasons'] = ['AQ_SOURCE_IDENTITY_CONFLICT']
        return result
    tokens = (record.raw_label or '').lower().split()
    if not tokens or len(set(tokens)) != len(tokens) or any(t not in COMPONENTS for t in tokens):
        result['reasons'] = ['AQ_LABEL_UNSUPPORTED']
        return result
    result['components'] = sorted(COMPONENTS[t] for t in tokens)
    if len(tokens) > 1:
        result.update(status='MIXED', reasons=['SOURCE_ARRAY_MIX_NOT_EXECUTION_RESOLVED'])
    elif tokens == ['tp']:
        result.update(status='UNSUPPORTED', reasons=['TOTAL_POWER_NOT_SUPPORTED'])
    elif antennas is None:
        result['reasons'] = ['ANTENNA_DIAMETERS_MISSING']
    elif antennas['diameters_m'] != [7.0 if tokens == ['7m'] else 12.0]:
        result.update(status='CONFLICT', reasons=['AQ_LABEL_AND_EXECUTION_DIAMETERS_DISAGREE'])
    else:
        result.update(status='BOUND', reasons=[])
    return result


def execution_readiness(execution, raw, catalog=None):
    if sha256(raw).hexdigest() != execution['evidence']['source_sha256']:
        raise ValueError('Setup listobs differs from verified execution')
    errors = {}
    try:
        windows = parse_spectral_windows(raw)
    except ValueError as exc:
        windows = {}
        errors['spectral_windows'] = str(exc)
    try:
        antennas = parse_antennas(raw)
    except ValueError as exc:
        antennas = None
        errors['antennas'] = str(exc)
    array = bind_array(catalog, member=execution['member_ous_uid'], source=execution['source_name'], antennas=antennas)
    fields = []
    for field in execution['evidence']['fields']:
        ids = sorted({sid for scan in field['scans'] for sid in scan['spw_ids']})
        missing = sorted(set(ids) - set(windows))
        linked = [windows[sid] for sid in ids if sid in windows]
        # Names are retained as explicit source labels, not an automatic observing-mode decision.
        full_res = [w['spw_id'] for w in linked if w['name'].endswith('#FULL_RES')]
        reasons = list(array['reasons'])
        if missing or not ids:
            reasons.append('SCIENCE_SPW_LINKS_INCOMPLETE')
        if not full_res:
            reasons.append('NO_EXPLICIT_FULL_RES_SCIENCE_SPW')
        if any(w['frame'] != 'TOPO' for w in linked):
            reasons.append('NON_TOPO_FREQUENCY_REQUIRES_FRAME_HANDLING')
        if antennas is None:
            reasons.append('ANTENNA_TABLE_UNAVAILABLE')
        if antennas is not None and len(antennas['diameters_m']) != 1:
            reasons.append('MIXED_DISH_EXECUTION')
        fields.append(dict(asdm_uid=execution['asdm_uid'], **field,
            spectral_windows=linked, missing_spw_ids=missing, explicit_full_res_spw_ids=full_res,
            input_status='EVIDENCE_BOUND' if not reasons else 'NOT_READY', blocking_reasons=sorted(set(reasons)),
            footprint_status='NOT_EVALUATED', footprint_requirements=[
                'SELECT_FREQUENCY_AND_SPW_POLICY', 'VALIDATE_CHANNEL_EDGE_REQUIREMENTS',
                'SELECT_PRIMARY_BEAM_MODEL_AND_THRESHOLD', 'VERIFY_FIELD_ANTENNA_PARTICIPATION']))
    return dict(asdm_uid=execution['asdm_uid'], listobs_sha256=sha256(raw).hexdigest(),
                spectral_window_count=len(windows), antenna_evidence=antennas, array_evidence=array,
                parse_errors=errors, fields=fields)


def build_readiness(directory: Path, *, array_catalog: Path | None = None):
    executions, provenance = load_package_executions(directory)
    catalog = load_archive_array_catalog(array_catalog) if array_catalog is not None else None
    sources = {e['asdm_uid']: e for e in provenance['execution_evidence']}
    reports = []
    for execution in executions:
        raw = (directory / sources[execution['asdm_uid']]['listobs_file']).read_bytes()
        reports.append(execution_readiness(execution, raw, catalog))
    return dict(schema_version='archive_mosaic_footprint_readiness_1',
        member_ous_uid=executions[0]['member_ous_uid'], source_name=executions[0]['source_name'],
        executions=reports, field_record_count=sum(len(e['fields']) for e in reports),
        provenance=provenance, footprint_status='NOT_EVALUATED',
        completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED')
