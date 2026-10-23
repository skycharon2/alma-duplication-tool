"""Reconcile saved Member/target inventory rows with verified execution evidence."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from alma_duplicate.archive_mosaic_pipeline import (
    MAX_METADATA_BYTES, read_mosaic_identity, read_mosaic_rows,
    reconstruct_acquired_execution,
)


def reconcile_inventory(metadata: Path, execution_dirs: list[Path], *, member: str,
                        source: str, capture_receipt: Path | None = None) -> dict:
    """Report coverage of supplied rows, without asserting an exhaustive TAP query.

    Repeated spectral-product rows collapse by ASDM within one project/Member/target.
    Execution fields remain execution-local and are never spatially deduplicated.
    """
    with metadata.open('rb') as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    capture_hash = None
    if capture_receipt is not None:
        from alma_duplicate.archive_mosaic_discovery import verify_inventory_capture
        verify_inventory_capture(raw, capture_receipt, member=member, source=source)
        capture_hash = sha256(capture_receipt.read_bytes()).hexdigest()
    rows = read_mosaic_rows(raw)
    if not rows:
        raise ValueError('Empty inventory does not establish Member coverage')
    if any(r['member_ous_uid'] != member or r['target_name'] != source for r in rows):
        raise ValueError('Inventory must contain exactly the requested Member and target')
    if len({r['proposal_id'] for r in rows}) != 1:
        raise ValueError('Inventory has conflicting project identities')
    expected = {r['asdm_uid']: r for r in rows}
    acquired = {}
    for directory in execution_dirs:
        identity = read_mosaic_identity((directory / 'metadata.xml').read_bytes())
        uid = identity['asdm_uid']
        if uid not in expected or expected[uid] != identity:
            raise ValueError('Execution identity is outside the supplied inventory')
        if uid in acquired:
            raise ValueError('Duplicate execution input; choose one evidence directory per ASDM')
        execution, acquisition_hash = reconstruct_acquired_execution(directory, identity)
        document_bytes = (directory / 'execution.json').read_bytes()
        document = json.loads(document_bytes)
        provenance = document.get('provenance', {})
        if (document.get('schema_version') != 'archive_mosaic_execution_2'
                or document.get('execution') != json.loads(json.dumps(asdict(execution)))
                or provenance != dict(metadata_file='metadata.xml',
                                      metadata_sha256=sha256((directory / 'metadata.xml').read_bytes()).hexdigest(),
                                      acquisition_file='acquisition.json',
                                      acquisition_sha256=acquisition_hash,
                                      listobs_file='listobs.txt')):
            raise ValueError('Saved execution differs from verified source evidence')
        acquired[uid] = dict(directory=str(directory), execution_sha256=sha256(document_bytes).hexdigest(),
                             science_field_count=len(execution.evidence.fields))
    missing = sorted(set(expected) - set(acquired))
    return dict(schema_version='archive_mosaic_inventory_1',
                member_ous_uid=member, source_name=source,
                project_code=rows[0]['proposal_id'],
                inventory_sha256=sha256(raw).hexdigest(), input_row_count=len(rows),
                expected_asdm_uids=sorted(expected), acquired=acquired,
                missing_asdm_uids=missing,
                coverage_status='MISSING_EXECUTIONS' if missing else 'SUPPLIED_INVENTORY_COVERED',
                inventory_scope=('CAPTURED_VISIBLE_SCIENCE_MOSAIC_MEMBER_TARGET' if capture_hash else
                                 'SAVED_ROWS_EXHAUSTIVENESS_NOT_ESTABLISHED'),
                capture_receipt_sha256=capture_hash,
                completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED')
