"""Read-only active Queue census; emits JSON to stdout, never writes the store."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from alma_duplicate.storage.queue_active import QueueActiveRegistry
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes

ap = argparse.ArgumentParser()
ap.add_argument('--store-root', default='data/cache/queue-snapshots')
a = ap.parse_args()
root = Path(a.store_root)
before = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*') if p.is_file()}
r = QueueActiveRegistry(root)
active = r.current()
if active is None:
    raise SystemExit('No validated active snapshot')
s = r.store.read_source(active['source_id'])
p = parse_queue_csv_bytes(s.raw_bytes, source_url=s.metadata['source_url'])
assert p.can_reconstruct and len(p.raw_rows) == len(p.row_inputs)
rows = p.row_inputs
fields = ['RA', 'Dec', 'Long Offset', 'Lat Offset', 'Mos. Coord.',
          'Mos. Length', 'Mos. Width', 'Mos. PA', 'Mos. Spacing']
def val(row, key):
    return row.raw_row.value(key).strip()
def line(row):
    return row.raw_row.row_id.physical_start_line
categories = {}
for kind in ('Custom', 'Rectangle', '', 'N/A'):
    rr = [x for x in rows if x.spatial.mosaic_raw == kind]
    stats = {}
    for f in fields:
        vs = [val(x, f) for x in rr]
        entry = {'populated': sum(bool(v) for v in vs)}
        if f != 'Mos. Coord.':
            nums = [float(v) for v in vs if v]
            entry.update(zero=sum(v == 0 for v in nums),
                         min=min(nums, default=None), max=max(nums, default=None))
        stats[f] = entry
    categories[kind or '<BLANK>'] = {
        'rows': len(rr), 'fields': stats,
        'frames': dict(Counter(val(x, 'Mos. Coord.') or '<BLANK>' for x in rr)),
        'offset_nonzero_exact': sum(any(float(val(x, f)) != 0 for f in ('Long Offset', 'Lat Offset')) for x in rr),
        'offset_nonzero_1e_6_arcsec': sum(any(abs(float(val(x, f))) > 1e-6 for f in ('Long Offset', 'Lat Offset')) for x in rr),
        'zero_ra_dec_pairs': sum(float(val(x, 'RA')) == 0 and float(val(x, 'Dec')) == 0 for x in rr),
        'array_flags': dict(Counter(f"7m={val(x, 'Use 7-m?')};TP={val(x, 'Use TP?')}" for x in rr)),
        'parsed_kinds': dict(Counter(str(x.spatial.mosaic_kind) for x in rr)),
        'example': ({'line': line(rr[0]), 'values': {f: val(rr[0], f) for f in ['Project Code', 'Target Name', 'Band'] + fields}} if rr else None),
    }
custom = [x for x in rows if x.spatial.mosaic_raw == 'Custom']
groups = defaultdict(list)
for row in custom:
    groups[tuple(val(row, k) for k in ('Project Code', 'Target Name', 'Band'))].append(row)
spatial = ['RA', 'Dec', 'Long Offset', 'Lat Offset', 'Mos. Coord.']
setup = [c for c in p.snapshot.operational_columns if c.startswith(('Freq SPW', 'Bandwidth SPW', 'Spec.Res.', 'SPS '))] + ['Ref.Frequency', 'Ref.Freq.Width', 'Req.Sensitivity', 'Req. Ang. Res.', 'Use 7-m?', 'Use TP?', 'Is Sky Freq?', 'Velocity', 'Vel. Frame', 'Vel. Convention', 'Polarization']
def unique(rr, ff):
    return len({tuple(val(x, f) for f in ff) for x in rr})
group_records = [{'key': list(k), 'row_count': len(rr), 'lines': [line(x) for x in rr],
                  'base_positions': unique(rr, ['RA', 'Dec']),
                  'spatial_tuples': unique(rr, spatial), 'setup_request_tuples': unique(rr, setup)}
                 for k, rr in sorted(groups.items())]
name_projects = defaultdict(set)
for row in custom:
    name_projects[val(row, 'Target Name')].add(val(row, 'Project Code'))
after = {str(q.relative_to(root)): sha256(q.read_bytes()).hexdigest()
         for q in root.rglob('*') if q.is_file()}
assert before == after, 'Store changed during audit'
print(json.dumps({'active': active, 'source_metadata': dict(s.metadata),
    'parser_version': p.snapshot.parser_version, 'schema_version': p.snapshot.schema_version,
    'status': str(p.status), 'row_count': len(rows), 'operational_columns': list(p.snapshot.operational_columns),
    'spatial_dictionary': [asdict(e) for e in p.snapshot.dictionary_entries if any(t in e.source_name for t in ('RA', 'Dec', 'Offset', 'Mos', 'Project', 'Target'))],
    'categories': categories, 'custom_diagnostic_groups': group_records,
    'custom_group_summary': {'project_target_band_buckets': len(groups),
        'multiple_base_position_buckets': sum(g['base_positions'] > 1 for g in group_records),
        'multiple_setup_request_buckets': sum(g['setup_request_tuples'] > 1 for g in group_records),
        'repeated_spatial_tuple_buckets': sum(g['spatial_tuples'] < g['row_count'] for g in group_records),
        'exact_content_unique': len({x.raw_row.content_fingerprint for x in custom}),
        'names_in_multiple_projects': {k: sorted(v) for k,v in sorted(name_projects.items()) if len(v) > 1}},
    'store_files_sha256_before_and_after': before, 'store_unchanged': True}, indent=2))
