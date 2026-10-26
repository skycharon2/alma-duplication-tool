"""Revalidate alternative pointing evidence for main-entry diagnostic reporting."""
from hashlib import sha256
import json
from pathlib import Path
import re

from alma_duplicate.archive_auxiliary import MAX_CANDIDATES, MAX_TEXT, select_auxiliary
from alma_duplicate.archive_mosaic_discovery import verify_inventory_capture
from alma_duplicate.parsers.archive_qa_text import inspect_qa_text


def alternative_diagnostics(candidate):
    """Never consume saved readiness claims or use QA coordinates as coverage."""
    result = dict(status='NO_ALTERNATIVE_EVIDENCE', sources=[], reasons=[])
    if not candidate.get('package_audit_dir'):
        return result
    directory = Path(candidate['package_audit_dir'])
    try:
        audit_path = directory/'package_audit.json'
        if not audit_path.exists():
            return result
        audit = json.loads(audit_path.read_text())
        entries = audit.get('inspection', {}).get('alternative_evidence', [])
        if not entries:
            return result
        if not isinstance(entries, list) or len(entries) > MAX_CANDIDATES:
            raise ValueError('Alternative evidence count invalid')
        member, source = candidate['member_ous_uid'], candidate['source_name']
        if (audit['member_ous_uid'], audit['source_name']) != (member, source):
            raise ValueError('Alternative evidence candidate identity mismatch')
        metadata = (directory/'metadata.xml').read_bytes()
        verify_inventory_capture(metadata, directory/'inventory_receipt.json', member=member, source=source)
        product, digest, _ = select_auxiliary(directory/'discovery.json', audit['product']['row_index'])
        if (product.member_ous_uid != member or digest != audit['discovery_receipt_sha256']
                or sha256(metadata).hexdigest() != audit['inventory_sha256']):
            raise ValueError('Alternative evidence receipt mismatch')
        seen = set()
        for entry in entries:
            digest = entry['sha256']
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Invalid alternative evidence hash')
            if digest in seen:
                continue
            seen.add(digest)
            with (directory/'listobs'/(digest+'.txt')).open('rb') as stream:
                raw = stream.read(MAX_TEXT+1)
            if len(raw) > MAX_TEXT or len(raw) != entry['bytes'] or sha256(raw).hexdigest() != digest:
                raise ValueError('Alternative evidence integrity mismatch')
            parsed = inspect_qa_text(raw, target_name=source)
            result['sources'].append(dict(sha256=digest, path_chain=entry['path_chain'],
                reported_asdm_uid=parsed.get('reported_asdm_uid'), status=parsed['status'],
                science_field_count=len(parsed['science_fields']),
                science_field_ids=[f['field_id'] for f in parsed['science_fields']],
                excluded_field_ids=[f['field_id'] for f in parsed['excluded_fields']],
                position_status='NOT_READY', reasons=parsed['reasons']))
        result.update(status='UNVERIFIED_ALTERNATIVE_EVIDENCE', reasons=sorted({
            reason for s in result['sources'] for reason in s['reasons']}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status='INVALID_ALTERNATIVE_EVIDENCE', sources=[], reasons=[str(exc)])
    return result


def position_summary(evaluated):
    """Expose per-context counts without treating absent coverage as zero coverage."""
    rows = []
    for context in evaluated.get('contexts', []):
        position = next((c for c in context.get('criteria', []) if c['criterion_id'] == 'POS-MOSAIC'), None)
        if position is None:
            continue
        coverage = context.get('coverage') or {}
        rows.append(dict(context_id=context.get('context_id'), outcome=position['outcome'],
            reasons=position.get('reasons', []), inside_count=coverage.get('inside_count'),
            pointing_count=coverage.get('pointing_count'),
            included_asdm_uids=coverage.get('included_asdm_uids', []),
            excluded_executions=coverage.get('excluded_executions', [])))
    return rows
