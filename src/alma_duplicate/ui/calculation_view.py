"""Readable projections of stored scientific steps; never evaluate a criterion."""

import json

from alma_duplicate.ui.report_view import DERIVED


def fact(label, value, unit=''):
    return {'label': label, 'value': value, 'unit': unit}


def _quantity(label, value):
    value = value or {}
    return fact(label, value.get('value'), value.get('unit', ''))


def _json_rows(text):
    try:
        rows = json.loads(text)
    except (ValueError, TypeError):
        return []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def calculation_view(record):
    """Expose only labelled stored operands, including explicit missing values.

    Explanatory text describes the recorded method family; it supplies no new
    operands, inferred units, thresholds, outcomes or missing conversions.
    """
    derived = dict(record.get('derived') or [])
    details = dict(record.get('details') or [])
    criterion = record.get('criterion_id')
    facts = [fact(DERIVED[key][0], value, DERIVED[key][1])
             for key, value in derived.items() if key in DERIVED]
    notes = []
    windows = []
    if criterion == 'LINE-RMS' and 'sigma_at_plan_mjy_beam' in derived:
        notes = [
            'Archive RMS is first scaled from its 10 km/s reference to the planned spectral resolution, then adjusted to the angular comparison basis.',
            'Spectral scaling: σplan = σ10 × √(10 km/s / Δvplan). Angular correction: σcomparison = σplan × (θproposed / θcandidate)².',
            'The Archive sensitivity is metadata, not a measurement of the achieved image noise.',
        ]
    elif criterion == 'LINE-RMS' and 'queue_rms_at_planned_resolution_mjy' in derived:
        facts.insert(0, _quantity('Queue requested RMS at reference width', record.get('candidate')))
        notes = [
            'The reference RMS and noise bandwidth belong to this Queue row. The spectral resolution belongs to this candidate SPW; these are different quantities.',
            'Spectral scaling: σplan = σreference × √(Breference / Δνplan). Angular correction: σcomparison = σplan × (θproposed / θcandidate)².',
            'Queue values retain their source unit mJy. The backend compares requested flux-density RMS at the requested angular resolution; these are not achieved image-noise measurements.',
        ]
    elif criterion == 'CONT-RMS' and 'aggregate_rms_mjy' in derived:
        facts.insert(0, _quantity('Queue requested RMS at reference width', record.get('candidate')))
        notes = [
            'Candidate nominal widths are mapped to usable widths by the recorded Queue method. Overlapping usable intervals are counted once in the aggregate bandwidth.',
            'Aggregate scaling: σaggregate = σreference × √(Breference / Baggregate). No angular RMS correction is applied in this continuum method.',
            'Queue mJy values use the backend requested-flux-density interpretation. Frequency-dependent system temperature is not modelled.',
        ]
        windows = _json_rows(details.get('spw_evidence_json'))
        if details.get('aggregate_bandwidth_complete') == 'False':
            notes.append('The usable interval evidence is incomplete. A partial bandwidth sum cannot substitute for the aggregate result.')
    elif criterion == 'POS-SINGLE' and 'candidate_radius_deg' in derived:
        notes = ['The search radius only retrieves candidates. This comparison uses the recorded angular separation and the candidate half-power beam radius, with its own frequency and antenna diameter.']
    elif criterion == 'LINE-RESOLUTION-COMPATIBILITY':
        notes = ['The candidate must support the planned spectral resolution. Smoothing can reduce spectral resolution; it cannot recover finer detail. Channel spacing and reference noise bandwidth do not replace spectral resolution.']
    elif criterion == 'LINE-COVERAGE':
        notes = ['The prepared proposed sky frequency is compared with this candidate window’s recorded coverage. Evidence from other windows is not substituted.']
    elif criterion == 'LINE-FDM':
        facts = [fact('Proposed correlator mode', details.get('proposed_mode')),
                 fact('Candidate correlator mode', details.get('candidate_mode', details.get('queue_mode')))]
        notes = ['The LINE check requires FDM evidence for both sides. Selecting a scientific purpose alone does not establish correlator mode.']
    return {'facts': facts, 'notes': notes, 'windows': windows}


def line_preparation(pair, request):
    """Bind raw inputs by the backend's setup/window/sensitivity identities."""
    attempt = pair.get('attempt') or {}
    prepared = attempt.get('proposed') or {}
    ref = attempt.get('reference') or {}
    raw = (request or {}).get('raw') or {}
    window_id = prepared.get('window_id')
    windows = [w for w in raw.get('spectral_windows', [])
               if w.get('window_id') == window_id and window_id is not None
               and raw.get('setup_id') == ref.get('proposed_setup_id')]
    facts = [fact('Proposed window', window_id)]
    if len(windows) == 1:
        window = windows[0]
        facts.append(_quantity('Entered centre frequency', window.get('center')))
        facts.append(fact('Frequency reference', (window.get('center') or {}).get('kind')))
        if (window.get('center') or {}).get('kind') == 'REST':
            facts.append(fact('Source redshift', raw.get('source_redshift')))
        if window.get('spectral_resolution') is not None:
            facts.append(_quantity('Entered window spectral resolution', window['spectral_resolution']))
        sensitivities = [s for s in raw.get('sensitivities', [])
                         if s.get('sensitivity_id') == prepared.get('sensitivity_id')
                         and prepared.get('sensitivity_id') is not None
                         and s.get('purpose') == 'LINE' and s.get('scope') == 'WINDOW'
                         and s.get('window_ids') == [window_id]
                         and s.get('setup_id') in (None, raw.get('setup_id'))]
        if len(sensitivities) == 1:
            facts.extend([_quantity('Entered planned spectral resolution', sensitivities[0].get('smoothing_resolution')),
                          _quantity('Entered planned RMS', sensitivities[0].get('rms'))])
    facts.extend([fact('Prepared sky frequency', prepared.get('sky_frequency_ghz'), 'GHz'),
                  fact('Prepared planned spectral resolution', prepared.get('planned_resolution_kms'), 'km/s')])
    spw = (attempt.get('candidate') or {}).get('spw') or {}
    if spw:
        frequency = spw.get('frequency_derivation') or {}
        facts.extend([
            fact('Queue SPW', spw.get('number')),
            fact('Queue source frequency', (spw.get('frequency_ghz') or {}).get('value'), 'GHz'),
            fact('Queue prepared sky frequency', frequency.get('sky_frequency_ghz'), 'GHz'),
            fact('Queue Doppler factor', frequency.get('doppler_factor')),
            fact('Queue velocity convention', frequency.get('velocity_convention_raw')),
            fact('Queue velocity frame', frequency.get('velocity_frame_raw')),
            fact('Queue nominal bandwidth', (spw.get('bandwidth_mhz') or {}).get('value'), 'MHz'),
            fact('Queue usable bandwidth', spw.get('usable_bandwidth_ghz'), 'GHz'),
        ])
    return facts
