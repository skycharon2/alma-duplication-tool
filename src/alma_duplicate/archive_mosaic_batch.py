"""Reconstruct execution-local evidence from a verified visible TAP inventory."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_auxiliary import select_auxiliary
from alma_duplicate.archive_mosaic_discovery import verify_inventory_capture
from alma_duplicate.archive_mosaic_inventory import reconcile_inventory
from alma_duplicate.archive_mosaic_pipeline import (
    MAX_METADATA_BYTES, NS, read_mosaic_rows, read_mosaic_identity, run_archive_mosaic_pipeline,
)
from alma_duplicate.clients.archive_products import discover_archive_products, parse_archive_products


def _save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _single_row(identity):
    root = ET.Element(NS + 'VOTABLE', version='1.3')
    resource = ET.SubElement(root, NS + 'RESOURCE', type='results')
    ET.SubElement(resource, NS + 'INFO', name='QUERY_STATUS', value='OK')
    table = ET.SubElement(resource, NS + 'TABLE')
    for name in identity:
        ET.SubElement(table, NS + 'FIELD', name=name, datatype='char', arraysize='*')
    row = ET.SubElement(ET.SubElement(ET.SubElement(table, NS + 'DATA'), NS + 'TABLEDATA'), NS + 'TR')
    for value in identity.values():
        ET.SubElement(row, NS + 'TD').text = value
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def run_batch(*, metadata: Path, capture_receipt: Path, member: str, source: str,
              cache: Path, output: Path, datalink_response: Path | None = None,
              reuse_dirs=(), offline=False):
    """Run a fresh batch; reuse only explicitly supplied, reverified executions.

    Downloads remain bounded by the existing auxiliary client. Multiple usable
    auxiliary products require explicit investigation and are never guessed.
    """
    with metadata.open('rb') as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    capture = verify_inventory_capture(raw, capture_receipt, member=member, source=source)
    identities = {r['asdm_uid']: r for r in read_mosaic_rows(raw)}
    # Validate reuse identity before any output or download; duplicate inputs are errors.
    reuse = {}
    for directory in reuse_dirs:
        identity = read_mosaic_identity((directory / 'metadata.xml').read_bytes())
        uid = identity['asdm_uid']
        if identities.get(uid) != identity or uid in reuse:
            raise ValueError('Unexpected or duplicate reuse execution')
        reuse[uid] = directory
    if offline and datalink_response is None and len(reuse) != len(identities):
        raise ValueError('Offline batch requires a saved DataLink response for new executions')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'metadata.xml').write_bytes(raw)
    (output / 'inventory_receipt.json').write_bytes(capture_receipt.read_bytes())
    report = dict(schema_version='archive_mosaic_batch_1', member_ous_uid=member,
                  source_name=source, inventory_sha256=sha256(raw).hexdigest(),
                  inventory_scope='CAPTURED_VISIBLE_SCIENCE_MOSAIC_MEMBER_TARGET',
                  expected_asdm_uids=sorted(identities), executions={},
                  completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED')
    products = output / 'products'
    products.mkdir()
    discovery_error = None
    selected = None
    if len(reuse) != len(identities):
        try:
            if datalink_response is not None:
                with datalink_response.open('rb') as stream:
                    product_raw = stream.read(MAX_METADATA_BYTES + 1)
                result = parse_archive_products(product_raw, member_ous_uid=member)
                url = None
            else:
                result, product_raw, url = discover_archive_products(member, origin=capture['request']['origin'])
            if product_raw is not None:
                (products / 'response.xml').write_bytes(product_raw)
            _save(products / 'discovery.json', dict(schema_version='archive_product_discovery_1',
                  response_file='response.xml', capture_truncated=result.response_bytes > MAX_METADATA_BYTES,
                  request_url=url, mode='OFFLINE_REPLAY' if datalink_response else 'LIVE_METADATA', discovery=asdict(result)))
            candidates = []
            for product in result.products:
                try:
                    select_auxiliary(products / 'discovery.json', product.row_index)
                    candidates.append(product.row_index)
                except ValueError:
                    pass
            if len(candidates) != 1:
                raise ValueError(f'Expected one usable auxiliary product; found {len(candidates)} ({result.status})')
            selected = candidates[0]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            discovery_error = str(exc)
    successful = []
    for uid, identity in sorted(identities.items()):
        key = sha256(uid.encode()).hexdigest()
        directory = reuse.get(uid, output / key)
        try:
            if uid not in reuse:
                if discovery_error:
                    raise ValueError(discovery_error)
                row_path = output / (key + '.xml')
                row_path.write_bytes(_single_row(identity))
                state = run_archive_mosaic_pipeline(metadata=row_path, receipt=products / 'discovery.json',
                    row_index=selected, cache=cache, output=directory, offline=offline)
                if state['status'] != 'RECONSTRUCTED':
                    raise ValueError('Execution pipeline: ' + state['status'])
            verified = reconcile_inventory(output / 'metadata.xml', [directory], member=member, source=source,
                                           capture_receipt=output / 'inventory_receipt.json')
            entry = verified['acquired'][uid]
            report['executions'][uid] = dict(status='REUSED' if uid in reuse else 'RECONSTRUCTED', **entry)
            successful.append(uid)
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
            report['executions'][uid] = dict(status='FAILED', directory=str(directory), error=str(exc))
        report['missing_asdm_uids'] = sorted(set(identities) - set(successful))
        report['status'] = 'IN_PROGRESS'
        _save(output / 'batch.json', report)
    report['status'] = 'VISIBLE_INVENTORY_COVERED' if not report['missing_asdm_uids'] else 'INCOMPLETE'
    _save(output / 'batch.json', report)
    return report
