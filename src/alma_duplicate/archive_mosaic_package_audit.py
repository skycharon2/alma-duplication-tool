"""Audit package execution evidence independently of TAP row coverage."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path

from alma_duplicate.archive_auxiliary import select_auxiliary, acquire_auxiliary, inspect_auxiliary
from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.archive_mosaic_pipeline import MAX_METADATA_BYTES, read_mosaic_rows
from alma_duplicate.archive_mosaic_discovery import verify_inventory_capture


def audit_package(*, metadata: Path, capture_receipt: Path, receipt: Path,
                  row_index: int, cache: Path, output: Path, member: str, source: str,
                  offline=True, reuse_dir: Path | None = None):
    """Reconstruct supported original MS records; never forge additional TAP rows."""
    with metadata.open('rb') as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    verify_inventory_capture(raw, capture_receipt, member=member, source=source)
    rows = read_mosaic_rows(raw)
    product, receipt_hash, _ = select_auxiliary(receipt, row_index)
    if product.member_ous_uid != member:
        raise ValueError('Package Member differs from inventory')
    previous = None
    if reuse_dir is not None:
        previous = json.loads((reuse_dir / 'package_audit.json').read_bytes())
        if (previous.get('schema_version') != 'archive_mosaic_package_audit_1'
                or previous.get('member_ous_uid') != member or previous.get('source_name') != source
                or previous.get('inventory_sha256') != sha256(raw).hexdigest()
                or previous.get('discovery_receipt_sha256') != receipt_hash):
            raise ValueError('Reuse audit scope or discovery evidence differs')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'metadata.xml').write_bytes(raw)
    (output / 'inventory_receipt.json').write_bytes(capture_receipt.read_bytes())
    for name in ('discovery.json', 'response.xml'):
        (output / name).write_bytes((receipt.parent / name).read_bytes())
    archive, download, reused = acquire_auxiliary(product, cache, offline=offline)
    if previous is not None and previous['download']['sha256'] != download['sha256']:
        raise ValueError('Reuse package archive hash differs')
    inspection, _ = inspect_auxiliary(archive, asdm_uid=rows[0]['asdm_uid'],
                                      source_name=source, capture_dir=output / 'listobs')
    report = dict(schema_version='archive_mosaic_package_audit_1', member_ous_uid=member,
                  source_name=source, inventory_sha256=sha256(raw).hexdigest(),
                  discovery_receipt_sha256=receipt_hash, product=asdict(product),
                  download=download, reused_cache=reused, inspection=inspection,
                  executions={}, unresolved=[], completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED',
                  policy_status='NOT_EVALUATED')
    grouped = {}
    for candidate in inspection['candidates']:
        uid = candidate.get('reported_asdm_uid')
        if not uid:
            report['unresolved'].append(dict(candidate=candidate, reason='UNRECOGNIZED_MS_HEADER'))
        elif candidate.get('measurement_set_variant') == 'ORIGINAL':
            grouped.setdefault(uid, []).append(candidate)
    reported = {c.get('reported_asdm_uid') for c in inspection['candidates']} - {None}
    for uid in sorted(reported - set(grouped)):
        report['unresolved'].append(dict(asdm_uid=uid, reason='NO_ORIGINAL_MS'))
    for uid, candidates in sorted(grouped.items()):
        if len(candidates) != 1:
            report['unresolved'].append(dict(asdm_uid=uid, reason='AMBIGUOUS_ORIGINAL_MS'))
            continue
        candidate = candidates[0]
        path = output / 'listobs' / (candidate['sha256'] + '.txt')
        try:
            execution = reconstruct_archive_mosaic(path.read_bytes(), project_code=rows[0]['proposal_id'],
                member_ous_uid=member, asdm_uid=uid, source_name=source,
                metadata_reference='discovery.json')
        except ValueError as exc:
            report['unresolved'].append(dict(asdm_uid=uid, reason=str(exc)))
            continue
        execution = replace(execution, metadata_status='MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND',
                            acquisition_status='VERIFIED_PACKAGE_LISTOBS')
        filename = sha256(uid.encode()).hexdigest() + '.json'
        document = dict(schema_version='archive_mosaic_package_execution_1', execution=asdict(execution),
                        provenance=dict(listobs_file=str(path.relative_to(output)), candidate=candidate,
                                        archive_sha256=download['sha256'], discovery_receipt_sha256=receipt_hash))
        encoded = (json.dumps(document, indent=2) + '\n').encode()
        state = 'RECONSTRUCTED'
        if previous is not None and uid in previous['executions']:
            old = previous['executions'][uid]
            if old.get('execution_file') != filename:
                report['unresolved'].append(dict(asdm_uid=uid, reason='UNSAFE_REUSE_EXECUTION_PATH'))
                continue
            old_path = reuse_dir / filename
            if old_path.exists():
                try:
                    saved = old_path.read_bytes()
                    old_candidate = document['provenance']['candidate']
                    evidence_path = reuse_dir / 'listobs' / (old_candidate['sha256'] + '.txt')
                    saved_evidence = evidence_path.read_bytes()
                    if (sha256(saved).hexdigest() != old.get('sha256')
                            or json.loads(saved) != json.loads(encoded)
                            or sha256(saved_evidence).hexdigest() != old_candidate['sha256']
                            or len(saved_evidence) != old_candidate['bytes']):
                        raise ValueError('Reuse execution or listobs evidence differs')
                    encoded = saved
                    state = 'REUSED'
                except (OSError, ValueError, TypeError) as exc:
                    report['unresolved'].append(dict(asdm_uid=uid, reason=str(exc)))
                    continue
        (output / filename).write_bytes(encoded)
        report['executions'][uid] = dict(status=state, execution_file=filename, sha256=sha256(encoded).hexdigest(),
                                        science_field_count=len(execution.evidence.fields))
    expected = {r['asdm_uid'] for r in rows}
    report['tap_asdm_uids'] = sorted(expected)
    report['additional_package_asdm_uids'] = sorted(set(report['executions']) - expected)
    report['missing_tap_asdm_uids'] = sorted(expected - set(report['executions']))
    report['status'] = ('UNRESOLVED' if report['unresolved'] or report['missing_tap_asdm_uids'] else
                        'ADDITIONAL_EXECUTIONS_FOUND' if report['additional_package_asdm_uids'] else 'NO_ADDITIONAL_EXECUTIONS')
    (output / 'package_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
