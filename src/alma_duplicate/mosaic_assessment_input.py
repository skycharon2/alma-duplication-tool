"""Load explicit Mosaic candidates from local verified package evidence."""
import hashlib
import json
from pathlib import Path
from alma_duplicate.archive_mosaic_readiness import build_readiness


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f'Invalid JSON number: {value}')


def load_candidates(path):
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Candidate manifest exceeds 1 MB')
    document = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(document,dict) or set(document) != {'schema_version','candidates'}:
        raise ValueError('Expected candidate manifest with schema_version and candidates')
    if document['schema_version'] != 'mosaic_candidates_1':
        raise ValueError('Unsupported candidate manifest version')
    rows = document['candidates']
    if not isinstance(rows,list) or not 1 <= len(rows) <= 100:
        raise ValueError('Supply 1 to 100 candidates')
    seen = set()
    for row in rows:
        required = {'context_id','member_ous_uid','source_name'}
        optional = {'package_audit_dir','array_catalog','selections'}
        if not isinstance(row,dict) or not required <= set(row) or set(row)-required-optional:
            raise ValueError('Invalid candidate fields')
        if any(not isinstance(row[k],str) or not row[k].strip() for k in required):
            raise ValueError('Candidate identities must be nonempty strings')
        if row['context_id'] in seen:
            raise ValueError('Duplicate candidate context ID')
        seen.add(row['context_id'])
        if set(row)&optional and not optional <= set(row):
            raise ValueError('Supply audit directory, array catalog and selections together, or omit all')
        if 'selections' in row:
            if not isinstance(row['selections'],list) or not 1 <= len(row['selections']) <= 128:
                raise ValueError('Evidence-backed candidate requires 1 to 128 selections')
            for key in ('package_audit_dir','array_catalog'):
                if not isinstance(row[key],str) or not row[key].strip():
                    raise ValueError('Evidence paths must be nonempty strings')
    candidates = []
    for row in rows:
        candidate = {k:row[k] for k in ('context_id','member_ous_uid','source_name')}
        if 'selections' in row:
            def resolve(value):
                p = Path(value)
                return p if p.is_absolute() else path.parent / p
            readiness = build_readiness(resolve(row['package_audit_dir']),array_catalog=resolve(row['array_catalog']))
            if (readiness['member_ous_uid'] != row['member_ous_uid'] or
                    readiness['source_name'] != row['source_name']):
                raise ValueError('Evidence belongs to another candidate')
            candidate.update(readiness=readiness,selections=row['selections'])
        candidates.append(candidate)
    return candidates, hashlib.sha256(raw).hexdigest()
