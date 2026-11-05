"""Same-report single-pointing display data; no queries or scientific verdicts."""
import math

from alma_duplicate.ui.report_view import context_identity, criterion_view, criterion_status, criterion_explanation

CHART_ROWS = 30


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def unique_record(records, name):
    found = [r for r in records if r.get('criterion_id') == name]
    return found[0] if len(found) == 1 else None


def fields(record, name):
    rows = (record or {}).get(name) or []
    result = {}
    for key, value in rows:
        result[key] = None if key in result else value
    return result


def position(value):
    if not isinstance(value, dict):
        return None
    ra, dec = value.get('ra_deg'), value.get('dec_deg')
    return (ra, dec) if number(ra) and number(dec) and 0 <= ra < 360 and -90 <= dec <= 90 else None


def sky_offset(origin, point):
    """Azimuthal equidistant display projection, east left and north up, arcsec.

    Handles RA wrap and the poles without a small-angle cos(dec) approximation.
    Coordinates behind the tangent hemisphere are not displayed.
    """
    a0, d0 = map(math.radians, origin)
    a, d = map(math.radians, point)
    delta = a - a0
    east = math.cos(d) * math.sin(delta)
    north = math.cos(d0) * math.sin(d) - math.sin(d0) * math.cos(d) * math.cos(delta)
    forward = math.sin(d0) * math.sin(d) + math.cos(d0) * math.cos(d) * math.cos(delta)
    if forward <= 0:
        return None
    length = math.hypot(east, north)
    scale = math.atan2(length, forward) / length if length > 1e-15 else 1
    return [-math.degrees(east * scale) * 3600, math.degrees(north * scale) * 3600]


def beam_outline(origin, center, radius):
    """Project the stored spherical half-power radius; do not derive a new beam."""
    a, d = map(math.radians, center)
    r = math.radians(radius)
    points = []
    for i in range(73):
        bearing = 2 * math.pi * i / 72
        # Cartesian tangent basis stays defined even at an exact celestial pole.
        center_vector = (math.cos(d)*math.cos(a), math.cos(d)*math.sin(a), math.sin(d))
        north = (-math.sin(d)*math.cos(a), -math.sin(d)*math.sin(a), math.cos(d))
        east = (-math.sin(a), math.cos(a), 0)
        x, y, z = [c*math.cos(r) + math.sin(r)*(n*math.cos(bearing) + e*math.sin(bearing))
                   for c, n, e in zip(center_vector, north, east)]
        lat = math.atan2(z, math.hypot(x, y))
        lon = math.atan2(y, x)
        projected = sky_offset(origin, (math.degrees(lon) % 360, math.degrees(lat)))
        if projected is None:
            return None
        points.append(projected)
    return points


def spatial_view(context, records, origin, evidence):
    record = unique_record(records, 'POS-SINGLE')
    missing = {'available': False, 'reason': 'Confirmed position evidence is unavailable for this comparison.'}
    if not record or not record.get('eligible_for_formal_aggregation'):
        return missing
    if record.get('method_version') == 'archive_pos_single_mosaic_s_region_1':
        from alma_duplicate.ui.region_display import saved_region_outline
        detail = fields(record, 'details')
        if (origin is None or not evidence or evidence.get('reference') != context['reference']
                or evidence.get('context_id') != context['context_id']
                or evidence.get('geometry') != 'MOSAIC'):
            return missing
        try:
            center, vertices = saved_region_outline(detail)
        except (ValueError, TypeError):
            return missing
        outline = [sky_offset(origin, vertex) for vertex in vertices]
        offset = sky_offset(origin, center)
        if offset is None or any(point is None for point in outline):
            return {'available': False, 'reason': 'Region lies outside the display projection hemisphere.'}
        return {'available': True, 'center': center, 'offset': offset, 'outline': outline,
                'sky_outline': vertices, 'coverage_source': 'ARCHIVE_S_REGION',
                'point_status': fields(record, 'derived').get('point_status'),
                'center_kind': 'REGION_DISPLAY_REFERENCE', 'radius_arcsec': None,
                's_region_sha256': detail.get('s_region_sha256'),
                'reason': 'Archive Mosaic s_region; region center is a display reference only.'}
    derived = fields(record, 'derived')
    center = position({'ra_deg': derived.get('candidate_ra_deg'), 'dec_deg': derived.get('candidate_dec_deg')})
    if context['reference']['source'] == 'ARCHIVE':
        detail = fields(record, 'details')
        if (not evidence or evidence.get('reference') != context['reference']
                or evidence.get('context_id') != context['context_id']
                or evidence.get('geometry') != 'SINGLE_FIELD'
                or detail.get('position_interpretation') != 'CONFIRMED_FIXED_CELESTIAL_ICRS_SCOPE'):
            return missing
        center = position(evidence.get('center'))
    if origin is None or center is None:
        return missing
    offset = sky_offset(origin, center)
    if offset is None:
        return {'available': False, 'reason': 'Position lies outside the display projection hemisphere.'}
    radius = derived.get('candidate_radius_deg')
    outline = beam_outline(origin, center, radius) if number(radius) and 0 < radius < 90 else None
    return {'available': True, 'center': list(center), 'offset': offset, 'outline': outline,
            'radius_arcsec': radius * 3600 if outline else None,
            'diameter_m': derived.get('antenna_diameter_m'),
            'frequency_ghz': derived.get('candidate_frequency_ghz'),
            'separation_arcsec': derived.get('separation_deg') * 3600 if number(derived.get('separation_deg')) else None,
            'reason': '' if outline else 'Half-power boundary is unavailable; only the recorded center is shown.'}


def continuum_coverage(context):
    """Display only the component bound to this saved Archive comparison."""
    from alma_duplicate.rules.numeric import explicit_unit_quantity
    saved = context.get('spectral_display') or {}
    reference = context.get('reference') or {}
    if (reference.get('source') != 'ARCHIVE' or saved.get('reference') != reference
            or saved.get('source') != 'frequency_support.assigned_component'):
        return []
    component = saved.get('component') or {}
    interval = component.get('frequency_interval') or {}
    if component.get('component_index') != reference.get('component_index'):
        return []
    low, high = interval.get('low'), interval.get('high')
    if not all(number(v) and v > 0 for v in (low, high)):
        return []
    low = explicit_unit_quantity(low, interval.get('unit'), 'GHz')
    high = explicit_unit_quantity(high, interval.get('unit'), 'GHz')
    if low is None or high is None or low >= high:
        return []
    return [dict(low=float(low), high=float(high), bandwidth_ghz=float(high-low),
                 resolution=component.get('resolution'), component_index=component['component_index'])]



def spectral_setup(context):
    """Full row-scoped support for exploration, never scientific aggregation."""
    import hashlib
    import json
    saved = context.get('spectral_setup_display') or {}
    reference = context.get('reference') or {}
    evidence = saved.get('evidence') or {}
    if (reference.get('source') != 'ARCHIVE' or saved.get('reference') != reference
            or evidence.get('raw_row_id') != reference.get('raw_row_id')):
        return None
    parsed = evidence.get('parse_result') or {}
    components = []
    for component in parsed.get('components', []):
        temporary = {'reference': {**reference, 'component_index': component.get('component_index')}}
        temporary['spectral_display'] = {
            'reference': temporary['reference'], 'source': 'frequency_support.assigned_component',
            'component': component}
        intervals = continuum_coverage(temporary) if (
            component.get('parse_status') == 'PARSED' and not component.get('validation_issues')) else []
        components.append({
            'index': component.get('component_index'), 'interval': intervals[0] if intervals else None,
            'center': component.get('displayed_center'), 'resolution': component.get('resolution'),
            'sensitivities': component.get('sensitivities', []),
            'polarization': component.get('polarization_products', []),
            'status': component.get('parse_status'),
        })
    if not components:
        return None
    scope = {k: v for k, v in reference.items() if k not in {'component_index', 'raw_row_id'}}
    identity = context.get('display_identity') or {}
    execution = {k: identity.get(k) for k in ('Member OUS', 'ASDM', 'Target')}
    # Raw TAP rows repeat a context-wide support across SPWs. Row identity is
    # provenance, not setup identity, when the execution identity is complete.
    if not all(isinstance(v, str) and v.strip() for v in execution.values()):
        execution = {'unresolved_row': reference.get('raw_row_id')}
    def semantic(value):
        if isinstance(value, dict):
            return {k: semantic(v) for k, v in value.items()
                    if k not in {'raw_value', 'normalized_value', 'raw_text', 'raw_token'}}
        if isinstance(value, list):
            return [semantic(v) for v in value]
        return value
    signature = hashlib.sha256(json.dumps(semantic(parsed), sort_keys=True).encode()).hexdigest()
    key = hashlib.sha256(json.dumps([scope, execution, signature], sort_keys=True).encode()).hexdigest()
    bound = continuum_coverage(context)
    return {'id': key, 'reference': scope, 'parser_version': parsed.get('parser_version'),
            'components': components, 'execution': execution, 'signature': signature,
            'source_rows': [reference.get('raw_row_id')],
            'selected_component': bound[0]['component_index'] if bound else None}


def spectral_view(records, intent, context=None):
    record = unique_record(records, 'LINE-COVERAGE' if intent == 'LINE' else 'CONT-FREQ')
    missing = {'available': False, 'reason': 'Recorded comparison frequencies are unavailable.'}
    if not record:
        return missing
    if intent == 'LINE':
        d = fields(record, 'derived')
        values = [d.get(k) for k in ('sky_frequency_ghz', 'interval_low_ghz', 'interval_high_ghz')]
        if not all(number(v) and v > 0 for v in values) or values[1] >= values[2]:
            return missing
        return {'available': True, 'kind': 'interval', 'proposed': values[0], 'low': values[1], 'high': values[2],
                'result': criterion_status(record)}
    p, c = record.get('proposed') or {}, record.get('candidate') or {}
    if not all(q.get('unit') == 'GHz' and number(q.get('value')) and q['value'] > 0 for q in (p, c)):
        return missing
    return {'available': True, 'kind': 'representative', 'proposed': p['value'], 'candidate': c['value'],
            'result': criterion_status(record), 'coverage': continuum_coverage(context or {})}


def visualization_data(data, plot_page=1):
    request = data['document'].get('request', {}).get('normalized') or {}
    origin = position(request.get('position')) if (request.get('position') or {}).get('frame') == 'ICRS' else None
    supported = request.get('target_kind') == 'FIXED' and request.get('geometry') == 'SINGLE_POINTING'
    items = []
    if supported:
        for index, context in zip(data['context_indices'], data['contexts']):
            for v, scope in enumerate(context.get('beam_variants') or [context]):
                intents = {b['branch'] for b in scope.get('branches', []) if b.get('status') == 'CRITERIA_MET'}
                if 'CONTINUUM' in intents:
                    items.append((index, v, None, context, scope.get('criteria', []), 'CONTINUUM', None))
                if 'LINE' in intents:
                    for p, pair in enumerate(scope.get('line_pairs', [])):
                        if pair.get('status') == 'CRITERIA_MET':
                            items.append((index, v, p, context, pair.get('criteria', []), 'LINE', pair))
    pages = max(1, (len(items) + CHART_ROWS - 1) // CHART_ROWS)
    if plot_page < 1 or plot_page > pages:
        raise IndexError('Visualization page unavailable')
    rows = []
    setups = {}
    for index, variant, pair_index, context, records, intent, pair in items[(plot_page-1)*CHART_ROWS:plot_page*CHART_ROWS]:
        identity = dict(context_identity(context))
        ref = ((pair or {}).get('attempt') or {}).get('reference') or {}
        association = ref.get('candidate_association') or {}
        spw = association.get('spw_token')
        if spw is None:
            spw = ref.get('spw_number', identity.get('SPW', 'Not recorded'))
        key = f'{index}-{variant}-{pair_index if pair_index is not None else "cont"}'
        anchor = f'context-{index}'
        if pair_index is not None:
            anchor = f'pair-{index}-' + (f'beam-{variant}-' if context.get('beam_variants') else '') + str(pair_index)
        label = ' · '.join(str(identity[k]) for k in ('Target', 'Project') if identity.get(k)) or f'Comparison {index + 1}'
        visible_records = list(records)
        if intent == 'CONTINUUM':
            visible_records = [r for r in data['document'].get('request_criteria', [])
                               if r.get('criterion_id') == 'CONT-SETUP'] + visible_records
        comparisons = []
        for record in visible_records:
            view = criterion_view(record)
            comparisons.append({'label': view['label'], 'proposed': view['proposed'],
                                'candidate': view['candidate'], 'result': criterion_status(record),
                                'reason': criterion_explanation(record)})
        row = {'id': key, 'display_number': (plot_page - 1) * CHART_ROWS + len(rows) + 1,
               'anchor': anchor, 'label': label, 'identity': identity,
               'source': context['reference']['source'], 'intent': intent, 'spw': str(spw),
               'window': ref.get('proposed_window_id'), 'beam_variant': variant if context.get('beam_variants') else None,
               'spatial': spatial_view(context, records, origin, data.get('spatial', {}).get(context['context_id'])),
               'spectral': spectral_view(records, intent, context),
               'criteria': comparisons}
        setup = spectral_setup(context)
        if setup:
            row['spectral_setup_id'] = setup['id']
            row['spectral_setup_component'] = setup.pop('selected_component')
            previous = setups.get(setup['id'])
            if previous:
                previous['source_rows'] = list(dict.fromkeys(previous['source_rows'] + setup['source_rows']))
            else:
                setups[setup['id']] = setup
        rows.append(row)
    return {'rows': rows, 'spectral_setups': setups, 'origin': list(origin) if origin else None, 'supported': supported,
            'plot_page': plot_page, 'plot_pages': pages, 'total': len(items),
            'spatial_available': sum(r['spatial']['available'] for r in rows),
            'spectral_available': sum(r['spectral']['available'] for r in rows),
            'continuum_declaration': any(r.get('method_version') == 'continuum_setup_declaration_1'
                                         for r in data['document'].get('request_criteria', [])),
            'start': (plot_page-1)*CHART_ROWS+1 if items else 0,
            'stop': min(plot_page*CHART_ROWS, len(items))}
