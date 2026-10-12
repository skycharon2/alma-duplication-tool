"""Read-only accounting for the published report JSON format.

Walk JSON-native values once without building a second serialized report. Byte
counts include indentation at the actual depth. Repetition fingerprints preserve
key order and scalar types, but ignore indentation and location.
"""
from collections import defaultdict
import hashlib
import json


def _scalar(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _pointer(parts):
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def analyze_report(document, *, top=30, min_repeat_bytes=4096):
    """Return exact formatted sizes and overlapping repeated-container examples.

    No mutation, deduplication, scientific evaluation or file writes. Group paths
    use '*' for list elements. Nested group/repetition sizes must not be summed.
    The input document is in memory; no claim of streaming JSON parsing is made.
    """
    if top < 1 or min_repeat_bytes < 1:
        raise ValueError('top and min_repeat_bytes must be positive')
    groups = defaultdict(lambda: {'occurrences': 0, 'bytes': 0})
    repeats = {}
    root_fields = {}

    def visit(value, path, group, depth):
        container = isinstance(value, (dict, list))
        if not container:
            raw = _scalar(value)
            size = compact = len(raw)
            digest = hashlib.sha256(b's' + raw).digest()
        else:
            mapping = isinstance(value, dict)
            fingerprint = hashlib.sha256(b'd' if mapping else b'l')
            size = compact = 2
            items = value.items() if mapping else enumerate(value)
            for key, child in items:
                if mapping and not isinstance(key, str):
                    raise TypeError('Report object keys must be strings')
                child_size, child_compact, child_hash = visit(
                    child, (*path, key), (*group, key if mapping else '*'), depth + 1)
                size += 1 + 2 * (depth + 1) + child_size
                compact += child_compact
                if mapping:
                    raw_key = _scalar(key)
                    size += len(raw_key) + 2
                    compact += len(raw_key) + 1
                    fingerprint.update(hashlib.sha256(raw_key).digest())
                fingerprint.update(child_hash)
                if depth == 0 and mapping:
                    root_fields[key] = child_size
            if value:
                size += len(value) - 1 + 1 + 2 * depth
                compact += len(value) - 1
            digest = fingerprint.digest()
            if compact >= min_repeat_bytes:
                entry = repeats.setdefault(digest, {
                    'occurrences': 0, 'total_formatted_bytes': 0,
                    'compact_bytes_per_copy': compact, 'example_paths': [],
                })
                entry['occurrences'] += 1
                entry['total_formatted_bytes'] += size
                if len(entry['example_paths']) < 2:
                    entry['example_paths'].append(_pointer(path))
        if 0 < depth <= 8:
            entry = groups[group]
            entry['occurrences'] += 1
            entry['bytes'] += size
        return size, compact, digest

    size, compact, _ = visit(document, (), (), 0)
    duplicates = []
    for entry in repeats.values():
        if entry['occurrences'] > 1:
            duplicates.append(dict(entry, repeated_compact_bytes=(
                entry['occurrences'] - 1) * entry['compact_bytes_per_copy']))
    duplicates.sort(key=lambda row: row['repeated_compact_bytes'], reverse=True)
    fields = sorted((dict(path=_pointer(path), **entry) for path, entry in groups.items()),
                    key=lambda row: row['bytes'], reverse=True)
    return {
        'schema_version': 1,
        'format': 'UTF-8; ensure_ascii=False; indent=2; trailing newline',
        'formatted_bytes': size + 1,
        'compact_bytes': compact + 1,
        'root_value_bytes': root_fields,
        'root_structure_bytes': size + 1 - sum(root_fields.values()),
        'largest_field_groups': fields[:top],
        'repeated_containers': duplicates[:top],
        'repetition_min_compact_bytes': min_repeat_bytes,
        'note': ('Nested field groups and repeated containers overlap; do not sum them. '
                 'Repeated compact bytes measure identical ordered content, not achievable '
                 'storage savings. References and schema changes would have their own costs. '
                 'No raw field values are included.'),
    }
