"""Read-only Mosaic comparisons from one stored result page."""
from alma_duplicate.ui.queue_browser import presentation
from alma_duplicate.ui.visualization import spectral_view


def _evidence(branch, criteria, pairs):
    intent = branch['branch']
    spectra = []
    if intent == 'LINE':
        for pair in pairs:
            if pair.get('status') == 'CRITERIA_MET' or pair.get('truth') == 'TRUE':
                spectra.append(spectral_view(pair.get('criteria', []), intent))
    else:
        spectra.append(spectral_view(criteria, intent))
    return dict(intent=intent, status=branch.get('status'), spectra=spectra)


def archive_rows(page):
    for entry in page['candidate_entries']:
        candidate = entry['candidate']
        for child in entry['contexts']:
            ctx = child['record']
            coverage = ctx.get('coverage') or {}
            if coverage.get('candidate_id') and coverage['candidate_id'] != ctx.get('context_id'):
                coverage = {}
            flags = {str(row.get('is_mosaic')).lower() for row in candidate.get('metadata_rows', [])
                     if row.get('member_ous_uid') == candidate.get('member_ous_uid')
                     and row.get('target_name') == candidate.get('source_name')}
            geometry = ('Single field' if coverage.get('candidate_geometry') == 'SINGLE_POINTING'
                        else 'Mosaic' if flags in ({'t'}, {'true'}) else 'Single field' if flags in ({'f'}, {'false'})
                        else 'Archive footprint')
            diameter = coverage.get('diameter_m')
            for branch in ctx.get('branches', []):
                if branch.get('status') != 'CRITERIA_MET':
                    continue
                yield dict(source='Archive', candidate=candidate.get('member_ous_uid') or 'Member unrecorded',
                           target=candidate.get('source_name'), geometry=geometry,
                           context_id=ctx.get('context_id'), array=f'{diameter:g} m' if diameter else '',
                           inside=coverage.get('inside_count'), total=coverage.get('pointing_count'),
                           outcome=coverage.get('outcome'), region=coverage.get('raw_s_region'),
                           beams=coverage.get('circles') or [],
                           probes=coverage.get('points') or (coverage.get('probes') or {}).get('points', []),
                           anchor=f"mosaic-context-{entry['candidate_index']}-{child['index']}",
                           **_evidence(branch, ctx.get('criteria', []), ctx.get('line_pairs', [])))


def queue_rows(page):
    for entry in presentation(page['document']):
        candidate = entry['candidate']
        position = candidate.get('position') or {}
        science = candidate.get('science') or {}
        for variant in science.get('variants', []):
            diameter = variant.get('diameter_m')
            positions = [p for p in position.get('beam_variants', []) if p.get('diameter_m') == diameter]
            saved = positions[0] if len(positions) == 1 else {}
            binding = saved.get('coverage') or {}
            bound = (binding.get('candidate_id') == candidate['candidate_id']
                     and bool(position.get('snapshot_sha256'))
                     and binding.get('snapshot_sha256') == position['snapshot_sha256']
                     and bool(position.get('source_row_ids'))
                     and binding.get('source_row_ids') == position['source_row_ids']
                     and binding.get('diameter_m') == diameter
                     and binding.get('association_confirmed') is True)
            probes = saved.get('points') if bound else None
            for branch in variant.get('branches', []):
                if branch.get('truth') != 'TRUE':
                    continue
                yield dict(source='Queue', candidate=candidate['candidate_id'], target=entry['target'],
                           geometry=entry['kind'], context_id=science.get('context_id'),
                           array=f'{diameter:g} m' if diameter else '', inside=saved.get('counts', {}).get('INSIDE') if bound else None,
                           total=len(probes) if probes is not None else None,
                           probes=probes or [], outcome=saved.get('outcome') if bound else None,
                           beams=binding.get('points', []) if bound else [], region=None,
                           anchor=f"queue-{candidate['candidate_id']}",
                           **_evidence(branch, variant.get('criteria', []), variant.get('line_pairs', [])))
