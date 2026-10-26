"""Connect saved TAP identity, auxiliary acquisition, and execution reconstruction."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_auxiliary import acquire_listobs, select_auxiliary
from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic

NS = '{http://www.ivoa.net/xml/VOTable/v1.3}'
MAX_METADATA_BYTES = 2_000_000


def read_mosaic_rows(raw: bytes) -> list[dict]:
    return read_candidate_rows(raw, mosaic_only=True)


def read_candidate_rows(raw: bytes, *, mosaic_only=False) -> list[dict]:
    """Read identified science TABLEDATA, optionally requiring Mosaic geometry."""
    if len(raw) > MAX_METADATA_BYTES or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported TAP metadata size or declarations')
    root = ET.fromstring(raw)
    if root.tag != NS + 'VOTABLE':
        raise ValueError('Unsupported VOTable namespace')
    resources = [r for r in root.findall(NS + 'RESOURCE') if r.get('type') == 'results']
    if len(resources) != 1:
        raise ValueError('Expected one TAP results resource')
    resource = resources[0]
    statuses = [i.get('value') for i in resource.findall(NS + 'INFO') if i.get('name') == 'QUERY_STATUS']
    if not statuses or any(s != 'OK' for s in statuses):
        raise ValueError('TAP response must declare successful QUERY_STATUS')
    tables = resource.findall(NS + 'TABLE')
    if len(tables) != 1:
        raise ValueError('Expected one TAP table')
    table = tables[0]
    names = [f.get('name') for f in table.findall(NS + 'FIELD')]
    required = ('proposal_id', 'member_ous_uid', 'asdm_uid', 'target_name', 'science_observation', 'is_mosaic')
    if len(set(names)) != len(names) or not set(required).issubset(names):
        raise ValueError('Missing or duplicate identity columns')
    data = table.findall(NS + 'DATA')
    if len(data) != 1 or len(data[0]) != 1 or data[0][0].tag != NS + 'TABLEDATA':
        raise ValueError('Only TAP TABLEDATA is supported')
    rows = list(data[0][0])
    result = []
    for element in rows:
        if element.tag != NS + 'TR':
            raise ValueError('Invalid TAP row element')
        cells = list(element)
        if len(cells) != len(names) or any(c.tag != NS + 'TD' for c in cells):
            raise ValueError('Invalid TAP row width')
        row = dict(zip(names, [''.join(c.itertext()).strip() for c in cells]))
        if any(not row[k] for k in required if k != 'is_mosaic') or row['science_observation'] != 'T' or (mosaic_only and row['is_mosaic'] != 'T'):
            raise ValueError('Expected identified science Mosaic observation')
        result.append({k: row[k] for k in required})
    return result


def read_mosaic_identity(raw: bytes) -> dict:
    """Accept one explicit science Mosaic TAP row; never choose among rows."""
    rows = read_mosaic_rows(raw)
    if len(rows) != 1:
        raise ValueError('Select exactly one TAP observation row')
    return rows[0]


def reconstruct_acquired_execution(output: Path, identity: dict):
    """Verify saved acquisition evidence before constructing an execution record."""
    if read_mosaic_identity((output / 'metadata.xml').read_bytes()) != identity:
        raise ValueError('Saved TAP identity changed')
    acquisition_bytes = (output / 'acquisition.json').read_bytes()
    acquisition = json.loads(acquisition_bytes)
    if acquisition.get('schema_version') != 'archive_listobs_acquisition_1' or acquisition.get('status') != 'FOUND':
        raise ValueError('Acquisition must contain one validated match')
    if acquisition['asdm_uid'] != identity['asdm_uid'] or acquisition['source_name'] != identity['target_name']:
        raise ValueError('Acquisition identity differs from TAP metadata')
    product, receipt_hash, requested = select_auxiliary(output / 'discovery.json', acquisition['product']['row_index'])
    if (json.loads(json.dumps(asdict(product))) != acquisition['product'] or product.member_ous_uid != identity['member_ous_uid']
            or receipt_hash != acquisition['discovery_receipt_sha256']
            or requested is not None and requested != identity['asdm_uid']):
        raise ValueError('Acquisition product binding mismatch')
    inspection = acquisition['inspection']
    selected = inspection['selected']
    matches = [c for c in inspection['candidates'] if c.get('status') == 'MATCHED']
    if (inspection['status'] != 'FOUND' or len(matches) != 1 or selected != matches[0]
            or not selected['path_chain']):
        raise ValueError('Acquisition selection is ambiguous or inconsistent')
    raw = (output / 'listobs.txt').read_bytes()
    if sha256(raw).hexdigest() != selected['sha256'] or len(raw) != selected['bytes']:
        raise ValueError('Extracted listobs integrity mismatch')
    result = reconstruct_archive_mosaic(
        raw, project_code=identity['proposal_id'], member_ous_uid=identity['member_ous_uid'],
        asdm_uid=identity['asdm_uid'], source_name=identity['target_name'],
        metadata_reference='metadata.xml',
    )
    if len(result.evidence.fields) != selected['science_field_count']:
        raise ValueError('Science field count differs from acquisition')
    return replace(result, metadata_status='SAVED_TAP_ROW_MEMBER_BOUND',
                   acquisition_status='VERIFIED_ACQUISITION_RECEIPT'), sha256(acquisition_bytes).hexdigest()


def run_archive_mosaic_pipeline(*, metadata: Path, receipt: Path, row_index: int,
                               cache: Path, output: Path, offline=False):
    """Run one scoped acquisition; failed source states never become empty objects."""
    with metadata.open('rb') as stream:
        raw_metadata = stream.read(MAX_METADATA_BYTES + 1)
    identity = read_mosaic_identity(raw_metadata)
    product, _, requested = select_auxiliary(receipt, row_index)
    if product.member_ous_uid != identity['member_ous_uid']:
        raise ValueError('TAP Member differs from discovery Member')
    if requested is not None and requested != identity['asdm_uid']:
        raise ValueError('TAP ASDM differs from discovery scope')
    acquisition = acquire_listobs(receipt, row_index, cache, output,
                                  asdm_uid=identity['asdm_uid'], source_name=identity['target_name'],
                                  offline=offline)
    (output / 'metadata.xml').write_bytes(raw_metadata)
    summary = dict(schema_version='archive_mosaic_pipeline_1', status=acquisition['status'],
                   metadata_sha256=sha256(raw_metadata).hexdigest(), identity=identity,
                   execution_file=None)
    if acquisition['status'] == 'FOUND':
        try:
            execution, receipt_hash = reconstruct_acquired_execution(output, identity)
            document = dict(schema_version='archive_mosaic_execution_2', execution=asdict(execution),
                            provenance=dict(metadata_file='metadata.xml',
                                            metadata_sha256=summary['metadata_sha256'],
                                            acquisition_file='acquisition.json',
                                            acquisition_sha256=receipt_hash,
                                            listobs_file='listobs.txt'))
            with (output / 'execution.json').open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(document, indent=2, allow_nan=False) + '\n')
            summary.update(status='RECONSTRUCTED', execution_file='execution.json')
        except (ValueError, KeyError, TypeError) as exc:
            summary.update(status='RECONSTRUCTION_FAILED', error=str(exc))
    (output / 'pipeline.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary
