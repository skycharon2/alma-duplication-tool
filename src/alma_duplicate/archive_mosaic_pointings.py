"""Diagnostic cross-execution comparison of reported ICRS field centres."""
from dataclasses import asdict, replace
from hashlib import sha256
from itertools import combinations
import json
import math
from pathlib import Path
from statistics import median

from alma_duplicate.archive_auxiliary import select_auxiliary
from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.archive_mosaic_discovery import verify_inventory_capture
from alma_duplicate.archive_mosaic_pipeline import read_mosaic_rows

MAX_PAIR_DISTANCES = 5_000_000


def load_package_executions(directory: Path):
    """Reparse saved listobs and check local provenance; do not claim remote authenticity."""
    audit_raw = (directory / 'package_audit.json').read_bytes()
    audit = json.loads(audit_raw)
    if (audit.get('schema_version') != 'archive_mosaic_package_audit_1'
            or audit.get('unresolved') or audit.get('missing_tap_asdm_uids')
            or audit.get('status') not in ('ADDITIONAL_EXECUTIONS_FOUND', 'NO_ADDITIONAL_EXECUTIONS')):
        raise ValueError('Require a resolved package audit')
    member, source = audit['member_ous_uid'], audit['source_name']
    metadata = (directory / 'metadata.xml').read_bytes()
    verify_inventory_capture(metadata, directory / 'inventory_receipt.json', member=member, source=source)
    rows = read_mosaic_rows(metadata)
    product, digest, _ = select_auxiliary(directory / 'discovery.json', audit['product']['row_index'])
    if (product.member_ous_uid != member or digest != audit['discovery_receipt_sha256']
            or json.loads(json.dumps(asdict(product))) != audit['product']
            or sha256(metadata).hexdigest() != audit['inventory_sha256']):
        raise ValueError('Package audit binding mismatch')
    candidates = {}
    for candidate in audit['inspection']['candidates']:
        if candidate.get('measurement_set_variant') == 'ORIGINAL':
            uid = candidate['reported_asdm_uid']
            if uid in candidates:
                raise ValueError('Ambiguous original MS')
            candidates[uid] = candidate
    if set(candidates) != set(audit['executions']):
        raise ValueError('Audit execution inventory differs from original MS candidates')
    executions, provenance = [], []
    for uid, entry in sorted(audit['executions'].items()):
        filename = sha256(uid.encode()).hexdigest() + '.json'
        if entry['execution_file'] != filename:
            raise ValueError('Unexpected execution filename')
        raw = (directory / filename).read_bytes()
        if sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Execution hash mismatch')
        document = json.loads(raw)
        candidate = candidates[uid]
        digest_text = candidate['sha256']
        if len(digest_text) != 64 or any(c not in '0123456789abcdef' for c in digest_text):
            raise ValueError('Invalid listobs hash')
        listobs_file = 'listobs/' + digest_text + '.txt'
        evidence = (directory / listobs_file).read_bytes()
        if sha256(evidence).hexdigest() != digest_text or len(evidence) != candidate['bytes']:
            raise ValueError('Listobs integrity mismatch')
        execution = reconstruct_archive_mosaic(evidence, project_code=rows[0]['proposal_id'],
            member_ous_uid=member, asdm_uid=uid, source_name=source, metadata_reference='discovery.json')
        execution = replace(execution, metadata_status='MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND',
                            acquisition_status='VERIFIED_PACKAGE_LISTOBS')
        expected = dict(schema_version='archive_mosaic_package_execution_1', execution=asdict(execution),
            provenance=dict(listobs_file=listobs_file, candidate=candidate,
                archive_sha256=audit['download']['sha256'], discovery_receipt_sha256=digest))
        if document != json.loads(json.dumps(expected)) or entry['science_field_count'] != len(execution.evidence.fields):
            raise ValueError('Execution content differs from parsed evidence')
        executions.append(document['execution'])
        provenance.append(dict(asdm_uid=uid, execution_file=filename, sha256=entry['sha256'],
                               listobs_file=listobs_file, listobs_sha256=digest_text))
    return executions, dict(package_audit_sha256=sha256(audit_raw).hexdigest(),
        archive_sha256=audit['download']['sha256'], execution_evidence=provenance,
        verification_scope='LOCAL_RECEIPTS_AND_REPARSED_LISTOBS_NO_ARCHIVE_RESCAN')


def separation_arcsec(a, b):
    """Stable great-circle angle, including wraparound and polar coordinates."""
    ra1, dec1, ra2, dec2 = map(math.radians, (a['ra_deg'], a['dec_deg'], b['ra_deg'], b['dec_deg']))
    delta = ra2 - ra1
    numerator = math.hypot(math.cos(dec2) * math.sin(delta),
        math.cos(dec1) * math.sin(dec2) - math.sin(dec1) * math.cos(dec2) * math.cos(delta))
    denominator = math.sin(dec1) * math.sin(dec2) + math.cos(dec1) * math.cos(dec2) * math.cos(delta)
    return math.degrees(math.atan2(numerator, denominator)) * 3600


def compare_pointings(executions: list[dict], *, tolerance_arcsec: float):
    """Keep every field; accept only isolated mutual nearest neighbours in tolerance.

    More than one neighbour inside tolerance is ambiguous even if one is closer.
    This is a diagnostic association, not physical pointing identity or deduplication.
    """
    if isinstance(tolerance_arcsec, bool) or not math.isfinite(tolerance_arcsec) or tolerance_arcsec <= 0:
        raise ValueError('Tolerance must be finite and positive in arcseconds')
    if len(executions) < 2:
        raise ValueError('At least two executions are required')
    scope = {(e['project_code'], e['member_ous_uid'], e['source_name']) for e in executions}
    if len(scope) != 1 or len({e['asdm_uid'] for e in executions}) != len(executions):
        raise ValueError('Require one scope and distinct ASDMs')
    for execution in executions:
        fields = execution['evidence']['fields']
        if not fields or len({f['field_id'] for f in fields}) != len(fields):
            raise ValueError('Empty or duplicate execution-local FIELD identifiers')
        for field in fields:
            if field['frame'] != 'ICRS' or field['target_name'] != execution['source_name']:
                raise ValueError('Unsupported coordinate frame or target')
            if (not math.isfinite(field['ra_deg']) or not math.isfinite(field['dec_deg'])
                    or not 0 <= field['ra_deg'] < 360 or not -90 <= field['dec_deg'] <= 90):
                raise ValueError('Invalid field coordinate')
    ordered = sorted(executions, key=lambda e: e['asdm_uid'])
    pair_cost = sum(len(a['evidence']['fields']) * len(b['evidence']['fields'])
                    for a, b in combinations(ordered, 2))
    if pair_cost > MAX_PAIR_DISTANCES:
        raise ValueError('Pairwise comparison budget exceeded')
    pairs = []
    for a, b in combinations(ordered, 2):
        left = sorted(a['evidence']['fields'], key=lambda f: f['field_id'])
        right = sorted(b['evidence']['fields'], key=lambda f: f['field_id'])
        matrix = [[separation_arcsec(x, y) for y in right] for x in left]
        forward = [[j for j, d in enumerate(row) if d <= tolerance_arcsec] for row in matrix]
        reverse = [[i for i in range(len(left)) if matrix[i][j] <= tolerance_arcsec] for j in range(len(right))]
        matches = []
        for i, js in enumerate(forward):
            if len(js) == 1:
                j = js[0]
                if (reverse[j] == [i] and matrix[i][j] == min(matrix[i])
                        and matrix[i][j] == min(row[j] for row in matrix)):
                    matches.append(dict(left_field_id=left[i]['field_id'], right_field_id=right[j]['field_id'],
                                        separation_arcsec=matrix[i][j]))
        matched_left = {m['left_field_id'] for m in matches}
        matched_right = {m['right_field_id'] for m in matches}

        def diagnostics(fields, other, distances, neighbours, matched):
            result = []
            for i, field in enumerate(fields):
                nearest = min(distances[i])
                result.append(dict(field_id=field['field_id'],
                    nearest_field_ids=[other[j]['field_id'] for j, d in enumerate(distances[i]) if abs(d - nearest) <= 1e-9],
                    nearest_separation_arcsec=nearest,
                    within_tolerance_field_ids=[other[j]['field_id'] for j in neighbours[i]],
                    status='MATCHED' if field['field_id'] in matched else 'UNMATCHED' if not neighbours[i] else 'AMBIGUOUS'))
            return result
        separations = [m['separation_arcsec'] for m in matches]
        pairs.append(dict(left_asdm_uid=a['asdm_uid'], right_asdm_uid=b['asdm_uid'], matches=matches,
            left_fields=diagnostics(left, right, matrix, forward, matched_left),
            right_fields=diagnostics(right, left, list(map(list, zip(*matrix))), reverse, matched_right),
            matched_count=len(matches), maximum_matched_separation_arcsec=max(separations) if separations else None,
            median_matched_separation_arcsec=median(separations) if separations else None))
    project, member, source = next(iter(scope))
    return dict(schema_version='archive_mosaic_pointing_comparison_1', project_code=project,
        member_ous_uid=member, source_name=source, tolerance_arcsec=tolerance_arcsec,
        matching_method='ISOLATED_MUTUAL_NEAREST_WITHIN_TOLERANCE',
        nearest_tie_epsilon_arcsec=1e-9, frame='ICRS',
        fields=[dict(asdm_uid=e['asdm_uid'], **f) for e in ordered for f in e['evidence']['fields']],
        field_record_count=sum(len(e['evidence']['fields']) for e in ordered), pairs=pairs,
        coordinate_scope='LISTOBS_REPORTED_FIELD_CENTRES_NOT_POINTING_TIMESERIES',
        completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED',
        deduplication_status='NOT_PERFORMED')
