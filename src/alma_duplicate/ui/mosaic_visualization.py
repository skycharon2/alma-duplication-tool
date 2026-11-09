"""Read-only Mosaic comparisons from one stored result page."""
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.ui.queue_browser import presentation
from alma_duplicate.ui.visualization import beam_outline, number, position, sky_offset, spectral_view
from alma_duplicate.ui.region_display import saved_region_outline
from alma_duplicate.ui.queue_geometry_visualization import _footprint
from alma_duplicate.ui.mosaic_frequency_view import (
    archive_spectral_setup as _archive_spectral_setup,
    queue_spectral_setup as _queue_spectral_setup,
    spectral_overview as _setup_overview,
)


def _evidence(branch, criteria, pairs):
    intent = branch['branch']
    spectra = []
    if intent == 'LINE':
        for pair in pairs:
            if pair.get('status') == 'CRITERIA_MET' or pair.get('truth') == 'TRUE':
                spectrum = spectral_view(pair.get('criteria', []), intent)
                attempt = pair.get('attempt') or {}
                reference = attempt.get('reference') or {}
                association = reference.get('candidate_association') or {}
                spectrum['window'] = attempt.get('proposed_window_id')
                spectrum['spw'] = association.get('spw_token', reference.get('spw_number'))
                spectra.append(spectrum)
    else:
        spectra.append(spectral_view(criteria, intent))
    return dict(intent=intent, status=branch.get('status'), spectra=spectra)


def _archive_project(entry, ctx):
    """Only expose a project bound to this Archive Member and target.

    An unassociated Member with several projects cannot safely select one.
    This is presentation data, not an input to scientific aggregation.
    """
    candidate = entry['candidate']
    projects = [p for p in (entry.get('identity') or {}).get('projects', [])
                if isinstance(p, str) and p.strip()]
    identity = ctx.get('display_identity') or {}
    project = identity.get('Project')
    if isinstance(project, str) and project.strip():
        if (identity.get('Member OUS') != candidate.get('member_ous_uid')
                or identity.get('Target') != candidate.get('source_name')):
            return None
        project = project.strip()
        return project if not projects or project in projects else None
    return projects[0] if len(projects) == 1 else None


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
                           project=_archive_project(entry, ctx),
                           target=candidate.get('source_name'), geometry=geometry,
                           context_id=ctx.get('context_id'), array=f'{diameter:g} m' if diameter else '',
                           inside=coverage.get('inside_count'), total=coverage.get('pointing_count'),
                           outcome=coverage.get('outcome'), region=coverage.get('raw_s_region'),
                           beams=coverage.get('circles') or [], footprint_evidence=coverage,
                           probes=coverage.get('points') or (coverage.get('probes') or {}).get('points', []),
                           spectral_setup=_archive_spectral_setup(
                               (candidate.get('spectral_setup_displays') or {}).get(ctx.get('context_id')) or ctx),
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
                           project=(entry.get('project') if entry.get('project') not in (None, 'Not recorded') else None),
                           geometry=entry['kind'], context_id=science.get('context_id'),
                           array=f'{diameter:g} m' if diameter else '', inside=saved.get('counts', {}).get('INSIDE') if bound else None,
                           total=len(probes) if probes is not None else None,
                           probes=probes or [], outcome=saved.get('outcome') if bound else None,
                           beams=binding.get('points', []) if bound else [], region=None,
                           footprint_evidence=dict(variant=saved, snapshot=position.get('snapshot_sha256'),
                                                   source_ids=position.get('source_row_ids')) if bound else {},
                           spectral_setup=_queue_spectral_setup(candidate),
                           anchor=f"queue-{candidate['candidate_id']}",
                           **_evidence(branch, variant.get('criteria', []), variant.get('line_pairs', [])))


def position_chart(row, proposed):
    """Project saved geometry for display only, preserving an equal angular scale."""
    missing = dict(available=False, reason='Confirmed footprint or proposed ICRS coordinates unavailable.')
    points = proposed.get('points') or []
    if not points or len(points) > 2000:
        return dict(missing, reason='No proposed pointings, or display limit of 2000 pointings exceeded.')
    if any(p.get('frame') != 'ICRS' or position(p) is None for p in points):
        return missing
    origin = position(points[0])
    offsets = [sky_offset(origin, position(p)) for p in points]
    evidence = row.get('footprint_evidence') or {}
    outlines = []
    if row['source'] == 'Queue':
        geometry, _ = _footprint(evidence.get('variant', {}), origin, 240, row['candidate'],
                                 evidence.get('snapshot'), evidence.get('source_ids'))
        if not geometry['available']:
            return dict(missing, reason=geometry['reason'])
        outlines = [p['outline'] for p in geometry['points']]
    elif evidence.get('raw_s_region'):
        try:
            _, vertices = saved_region_outline(evidence)
        except (ValueError, TypeError):
            return dict(missing, reason='Saved Archive region cannot be verified or displayed.')
        outlines = [[sky_offset(origin, p) for p in vertices]]
    elif row.get('beams'):
        if len(row['beams']) > 240:
            return dict(missing, reason='Footprint exceeds display limit of 240 beams.')
        for beam in row['beams']:
            radius = beam.get('radius_arcsec')
            if beam.get('frame') != 'ICRS' or position(beam) is None or not number(radius) or not 0 < radius < 324000:
                return missing
            outlines.append(beam_outline(origin, position(beam), radius / 3600))
    if not outlines:
        return missing
    if any(p is None for p in offsets) or any(o is None or any(p is None for p in o) for o in outlines):
        return dict(missing, reason='Geometry extends outside the display projection hemisphere.')
    # Proposed beam models use the proposal's array, never the candidate's array.
    diameter = {'7m': 7., '12m': 12.}.get(proposed.get('array'))
    frequencies = sorted({sp['proposed'] for sp in row.get('spectra', []) if sp.get('available')})
    proposal_beams = []
    beam_note = ''
    if diameter is None or not frequencies:
        beam_note = 'Proposed beam circles unavailable: proposal array or requested sky frequency is missing.'
    elif len(frequencies) * len(points) > 2000:
        beam_note = 'Proposed beam circles exceed the display limit of 2000; all pointing centres remain shown.'
    else:
        for frequency in frequencies:
            radius = primary_beam_fwhm_deg(frequency, diameter) * 1800
            projected = [beam_outline(origin, position(p), radius / 3600) for p in points]
            if any(o is None for o in projected):
                beam_note = 'Proposed beams extend outside the display projection hemisphere.'
                proposal_beams = []
                break
            proposal_beams.append(dict(frequency=frequency, radius=radius, outlines=projected))
    all_points = offsets + [p for outline in outlines for p in outline]
    all_points += [p for beam in proposal_beams for outline in beam['outlines'] for p in outline]
    left, right = min(p[0] for p in all_points), max(p[0] for p in all_points)
    bottom, top = min(p[1] for p in all_points), max(p[1] for p in all_points)
    span = max(right-left, top-bottom, 1)
    scale = 300 / span

    def pixel(p):
        return [245 + (p[0]-(left+right)/2)*scale, 210 - (p[1]-(bottom+top)/2)*scale]

    ticks = [dict(pixel=95+i*75, east=-((left+right)/2 + (i-2)*span/4),
                  north=(bottom+top)/2 - (i-2)*span/4, y=60+i*75) for i in range(5)]
    for beam in proposal_beams:
        beam['outlines'] = [' '.join(f'{x:.3f},{y:.3f}' for x,y in map(pixel,o)) for o in beam['outlines']]
    return dict(available=True, ticks=ticks, proposal_beams=proposal_beams, beam_note=beam_note, diameter=diameter, outlines=[' '.join(f'{x:.3f},{y:.3f}' for x,y in map(pixel,o)) for o in outlines],
                points=[dict(id=p['id'], xy=pixel(offset), ra=p['ra_deg'], dec=p['dec_deg']) for p,offset in zip(points,offsets)],
                scale_arcsec=span/2, origin=origin)


def frequency_chart(spectrum):
    if not spectrum.get('available'):
        return None
    values = [spectrum['proposed']]
    values += ([spectrum['low'], spectrum['high']] if spectrum['kind'] == 'interval' else [spectrum['candidate']])
    low, high = min(values), max(values)
    padding = max((high-low)*.15, high*1e-6)
    low, high = low-padding, high+padding
    return dict(low=low, high=high, x=[135+(value-low)/(high-low)*430 for value in values],
                ticks=[dict(x=135+i*107.5, value=low+(high-low)*i/4) for i in range(5)])


def spectral_overview(spectra, setup=None):
    """Full recorded setup plus saved matching comparisons; never infer SPWs."""
    return _setup_overview(spectra, setup)
