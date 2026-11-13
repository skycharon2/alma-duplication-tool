"""Mosaic-only, read-only frequency setup projection for report exploration.

This view uses already saved, source-bound evidence. It does not parse an ALMA
observation, decide matching, infer SPWs, or change the original report.
"""
import math

from alma_duplicate.ui.visualization import spectral_setup

MAX_DISPLAY_COMPONENTS = 128


def _positive_interval(low, high):
    return (all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) and v > 0 for v in (low, high))
            and low < high)


def archive_spectral_setup(context):
    """Normalize the Single Pointing-compatible *bound* Archive saved display."""
    reference = context.get('source_reference') or context.get('reference')
    if not reference or not context.get('spectral_setup_display'):
        return None
    saved = spectral_setup({
        'reference': reference,
        'display_identity': context.get('display_identity') or {},
        'spectral_setup_display': context['spectral_setup_display'],
    })
    if saved is None:
        return None
    components = []
    for comp in saved['components']:
        interval = comp.get('interval') or {}
        components.append(dict(
            label=f"Component {comp.get('index', 'unrecorded')}",
            low=interval.get('low'), high=interval.get('high'),
            status=comp.get('status') or 'NOT_RECORDED',
            resolution=comp.get('resolution'), sensitivities=comp.get('sensitivities', []),
            polarization=comp.get('polarization', []),
        ))
    return dict(id=saved['id'], source='Archive',
                label='Archive recorded frequency_support components',
                components=components,
                note='Parsed, row-bound Archive frequency_support; not a scientific verdict.')


def queue_spectral_setup(candidate):
    """Reject Queue setups with foreign candidate, snapshot or raw-row identity."""
    science = candidate.get('science') or {}
    saved = science.get('spectral_setup_display') or {}
    position = candidate.get('position') or {}
    rows = candidate.get('source_rows') or []
    ids = [row.get('source_row_id') for row in rows]
    if (saved.get('schema_version') != 'mosaic_queue_regular_spws_display_1'
            or not ids or not all(isinstance(v, str) and v for v in ids)
            or saved.get('candidate_id') != candidate.get('candidate_id')
            or not position.get('snapshot_sha256')
            or saved.get('snapshot_sha256') != position.get('snapshot_sha256')
            or saved.get('source_row_ids') != ids
            or position.get('source_row_ids') != ids
            or saved.get('representative_source_row_id') not in ids):
        return None
    components = [dict(label=f"SPW {spw.get('number', 'unknown')}",
                       low=spw.get('nominal_low_ghz'),
                       high=spw.get('nominal_high_ghz'),
                       usable_low=spw.get('usable_low_ghz'),
                       usable_high=spw.get('usable_high_ghz'),
                       status='NOMINAL_SKY_INTERVAL')
                  for spw in saved.get('spws', []) if isinstance(spw, dict)]
    if not components:
        return None
    return dict(id=str(candidate['candidate_id'])+':'+saved['snapshot_sha256'],
                source='Queue', label='Queue CSV nominal SKY SPW intervals',
                components=components,
                note='Saved CSV regular-SPW nominal and usable intervals; reference windows, not separate matching comparisons.')


def spectral_overview(spectra, setup=None):
    """Place the full *recorded* setup and matching comparisons on one GHz axis.

    Invalid components remain explicit unavailable rows. Oversize setup evidence
    is never silently truncated; the matching comparison plot remains usable.
    """
    available = [sp for sp in spectra if sp.get('available')]
    setup_rows = []
    setup_label = None
    setup_note = 'Full setup evidence not retained in this saved report; showing matching comparisons only.'
    if setup:
        source_rows = setup.get('components') or []
        if len(source_rows) > MAX_DISPLAY_COMPONENTS:
            setup_note = f'Full setup exceeds the display limit of {MAX_DISPLAY_COMPONENTS} components; matching comparisons only.'
        else:
            setup_rows = list(source_rows)
            setup_label = setup.get('label')
            setup_note = setup.get('note') or ''
    values = []
    for sp in available:
        values.append(sp['proposed'])
        values.extend([sp['low'], sp['high']] if sp['kind'] == 'interval' else [sp['candidate']])
        for interval in sp.get('coverage', []):
            if _positive_interval(interval.get('low'), interval.get('high')):
                values.extend((interval['low'], interval['high']))
    for comp in setup_rows:
        if _positive_interval(comp.get('low'), comp.get('high')):
            values.extend((comp['low'], comp['high']))
    if not values:
        return None
    low, high = min(values), max(values)
    padding = max((high-low)*.15, high*1e-6)
    low, high = low-padding, high+padding

    def x(value):
        return 135+(value-low)/(high-low)*430

    projected = []
    for i, comp in enumerate(setup_rows):
        valid = _positive_interval(comp.get('low'), comp.get('high'))
        projected.append(dict(label=comp.get('label') or f'Component {i+1}',
                              status=comp.get('status') or 'UNRECORDED',
                              low=x(comp['low']) if valid else None,
                              high=x(comp['high']) if valid else None,
                              raw_low=comp.get('low'), raw_high=comp.get('high'),
                              usable_low=comp.get('usable_low'), usable_high=comp.get('usable_high'),
                              resolution=comp.get('resolution'), sensitivities=comp.get('sensitivities', []),
                              polarization=comp.get('polarization', []),
                              y=116+i*34))
    # A compact setup summary occupies the first row. The individual recorded
    # components and saved matching comparisons are disclosed below it, like
    # the expandable Setup row in the Single Pointing spectral chart.
    first_matching_y = 116+len(projected)*34+(28 if projected else -56)
    rows = []
    for i, sp in enumerate(spectra):
        if not sp.get('available'):
            continue
        rows.append(dict(number=i+1, spw=sp.get('spw'), proposed=x(sp['proposed']),
                         low=x(sp['low']) if sp['kind'] == 'interval' else x(sp['candidate']),
                         high=x(sp['high']) if sp['kind'] == 'interval' else x(sp['candidate']),
                         coverage=[dict(interval, low=x(interval['low']), high=x(interval['high']),
                                        raw_low=interval['low'], raw_high=interval['high'])
                                   for interval in sp.get('coverage', [])
                                   if _positive_interval(interval.get('low'), interval.get('high'))],
                         kind=sp['kind'], y=first_matching_y+len(rows)*38))
    height = max(155, first_matching_y+len(rows)*38+52)
    # SVG is fully rendered server-side for accessible no-JS evidence. On load,
    # the browser collapses verified setup rows into a compact single row; click
    # expands the same saved comparison data without re-querying or re-evaluating.
    return dict(rows=rows, setup_rows=projected, setup_label=setup_label,
                setup_note=setup_note, matching_label_y=first_matching_y-19 if projected else None,
                height=height, collapsed_height=154 if projected else height,
                valid_setup_count=sum(row['low'] is not None for row in projected),
                ticks=[dict(x=135+i*107.5, value=low+(high-low)*i/4) for i in range(5)])
