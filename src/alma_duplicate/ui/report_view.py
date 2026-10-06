"""Display projections of stored criteria; no scientific calculation or aggregation."""

LABELS = {
    "POS-SINGLE": "Position", "ANGULAR": "Angular resolution",
    "CONT-SETUP": "Proposed continuum setup", "CONT-FREQ": "Representative frequency",
    "CONT-RMS": "Aggregate RMS", "LINE-FDM": "Correlator mode",
    "LINE-COVERAGE": "Frequency coverage",
    "LINE-RESOLUTION-COMPATIBILITY": "Spectral resolution", "LINE-RMS": "LINE RMS",
}

# Explicit units only. Unknown keys retain their backend names with no inferred unit.
DERIVED = {
    "separation_deg": ("Angular separation", "deg"),
    "candidate_radius_deg": ("Candidate beam radius", "deg"),
    "candidate_fwhm_deg": ("Candidate beam FWHM", "deg"),
    "candidate_frequency_ghz": ("Candidate beam frequency", "GHz"),
    "antenna_diameter_m": ("Antenna diameter", "m"),
    "candidate_ra_deg": ("Candidate RA", "deg"),
    "candidate_dec_deg": ("Candidate Dec", "deg"),
    "proposal_ra_deg": ("Proposed RA", "deg"),
    "proposal_dec_deg": ("Proposed Dec", "deg"),
    "sky_frequency_ghz": ("Prepared proposed sky frequency", "GHz"),
    "interval_low_ghz": ("Candidate interval lower bound", "GHz"),
    "interval_high_ghz": ("Candidate interval upper bound", "GHz"),
    "archive_resolution_kms": ("Archive spectral resolution", "km/s"),
    "planned_resolution_kms": ("Planned spectral resolution", "km/s"),
    "planned_resolution_mhz": ("Planned spectral resolution at the line frequency", "MHz"),
    "queue_resolution_mhz": ("Queue spectral resolution", "MHz"),
    "sigma_10kms_mjy_beam": ("Archive RMS at 10 km/s", "mJy/beam"),
    "sigma_at_plan_mjy_beam": ("Archive RMS at planned resolution", "mJy/beam"),
    "sigma_comp_mjy_beam": ("Archive RMS after angular correction", "mJy/beam"),
    "sigma_requested_mjy_beam": ("Requested RMS", "mJy/beam"),
    "queue_reference_width_mhz": ("Queue reference noise bandwidth", "MHz"),
    "queue_rms_at_planned_resolution_mjy": ("Queue RMS at planned resolution", "mJy"),
    "comparable_queue_rms_mjy": ("Queue RMS after angular correction", "mJy"),
    "theta_plan_arcsec": ("Planned angular resolution", "arcsec"),
    "theta_archive_arcsec": ("Archive angular resolution", "arcsec"),
    "theta_queue_arcsec": ("Queue angular resolution", "arcsec"),
    "reference_bandwidth_mhz": ("Queue reference noise bandwidth", "MHz"),
    "aggregate_bandwidth_mhz": ("Queue aggregate usable bandwidth", "MHz"),
    "aggregate_rms_mjy": ("Queue aggregate RMS", "mJy"),
    "qualifying_windows": ("Qualifying windows", ""),
    "unresolved_windows": ("Unresolved windows", ""),
    "threshold_ghz": ("Usable bandwidth threshold", "GHz"),
    "factor": ("Comparison factor", ""), "max_factor": ("Maximum factor", ""),
}


def criterion_view(record):
    """Keep the original record intact and project only explicitly stored evidence."""
    details = dict(record.get("details", []))
    derived = dict(record.get("derived", []))
    proposed, candidate = record.get("proposed"), record.get("candidate")
    if record["criterion_id"] == "LINE-FDM":
        proposed = {"value": details.get("proposed_mode"), "unit": ""}
        candidate = {"value": details.get("candidate_mode", details.get("queue_mode")), "unit": ""}
    if record["criterion_id"] == "LINE-COVERAGE" and candidate is None:
        low, high = derived.get("interval_low_ghz"), derived.get("interval_high_ghz")
        if low is not None and high is not None:
            candidate = {"value": f"{display_number(low)} – {display_number(high)}", "unit": "GHz",
                         "semantics": "Candidate interval from backend"}
    if record['criterion_id'] == 'LINE-RMS':
        # Show the comparable backend result, including an explicit unavailable value.
        key, unit = ('comparable_queue_rms_mjy', 'mJy') if 'comparable_queue_rms_mjy' in derived else ('sigma_comp_mjy_beam', 'mJy/beam')
        candidate = {'value': derived.get(key), 'unit': unit,
                     'semantics': 'At the requested spectral resolution and backend angular comparison basis'}
    return {
        "record": record, "label": LABELS.get(record["criterion_id"], "Additional criterion"),
        "proposed": proposed, "candidate": candidate,
        "derived": [
            {"key": key, "label": DERIVED.get(key, (key, ""))[0],
             "unit": DERIVED.get(key, (key, ""))[1], "value": value}
            for key, value in record.get("derived", [])
        ],
    }


def pair_binding(pair):
    """Expose the exact binding, including zero-valued SPW indices."""
    ref = pair["attempt"].get("reference") or {}
    fields = [("Proposed setup", ref.get("proposed_setup_id")),
              ("Proposed window", ref.get("proposed_window_id")),
              ("Proposed sensitivity", ref.get("proposed_sensitivity_id"))]
    association = ref.get("candidate_association") or {}
    if association:
        fields.extend((key, value) for key, value in (association.get("context") or {}).items())
        fields.extend((key, association.get(key)) for key in ("spw_token", "spw_index"))
    fields.extend((key, ref.get(key)) for key in ("source_row_id", "spw_number", "snapshot_sha256"))
    component = ref.get("candidate_component") or {}
    fields.extend((key, value) for key, value in component.items())
    return [(key, value) for key, value in fields if value is not None]


STATUS_LABELS = {
    'CRITERIA_MET': 'Meets these conditions',
    'CRITERIA_NOT_MET': 'Does not meet these conditions',
    'INDETERMINATE': 'Needs review',
    'SATISFIED': 'Satisfied', 'NOT_SATISFIED': 'Not satisfied',
    'Not computed': 'Not computed',
}


def display_number(value):
    """Round only the display; original evidence and decisions remain untouched."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(value, '.6g')
    return value


def _identity_values(context):
    """Collect exact stored identities without parsing generated IDs or joined labels."""
    fields = {}

    def add(label, value):
        if value is not None and value != '':
            fields.setdefault(label, [])
            if str(value) not in fields[label]:
                fields[label].append(str(value))

    for label, value in (context.get('display_identity') or {}).items():
        add(label, value)
    for record in (context.get('array_evidence') or {}).get('records', []):
        add('Target', record.get('source_name'))
        add('Member OUS', record.get('member_ous_uid'))
    for scope in context.get('beam_variants') or [context]:
        for pair in scope.get('line_pairs', []):
            ref = pair.get('attempt', {}).get('reference') or {}
            association = ref.get('candidate_association') or {}
            identity = association.get('context') or {}
            add('Target', identity.get('source_name'))
            add('Member OUS', identity.get('member_ous_uid'))
            add('ASDM', identity.get('asdm_uid'))
            add('SPW', association.get('spw_token'))
            add('SPW', ref.get('spw_number'))
            add('Queue row', ref.get('source_row_id'))
    return fields


def context_identity(context):
    """Use stored exact identities, including old reports; never parse generated IDs."""
    return [(label, ', '.join(values)) for label, values in _identity_values(context).items()]


def member_groups(entries):
    """Group presentation only; keep every context and its original index intact.

    Only an unambiguous Archive Member identity joins records. Missing or
    conflicting source/execution identities retain separate child contexts.
    Queue contexts remain independent and never acquire an Archive identity.
    """
    groups = {}
    for index, context in entries:
        identity = _identity_values(context)

        def one(label):
            values = identity.get(label, [])
            return values[0] if len(values) == 1 else None

        source = context.get('reference', {}).get('source')
        member = one('Member OUS') if source == 'ARCHIVE' else None
        key = ('ARCHIVE', member) if member else ('context', index)
        if key not in groups:
            groups[key] = {
                'anchor': f'member-{index}', 'member': member, 'source': source,
                'label': member or (f'Queue comparison {index + 1}' if source == 'QUEUE'
                                    else f'Archive comparison {index + 1}' if source == 'ARCHIVE'
                                    else f'Comparison {index + 1}'),
                'projects': [], 'children': {}, 'entries': [],
            }
        group = groups[key]
        for project in identity.get('Project', []):
            if project not in group['projects']:
                group['projects'].append(project)
        target, execution = one('Target'), one('ASDM')
        child_key = (target, execution) if member and target and execution else ('context', index)
        child = group['children'].setdefault(child_key, {
            'target': target, 'execution': execution, 'entries': [],
        })
        child['entries'].append((index, context))
        group['entries'].append((index, context))
    result = list(groups.values())
    for group in result:
        group['children'] = list(group['children'].values())
    return result


def report_summary(document):
    """Count stored context branch results; no new observation-level verdict."""
    request = document.get('request') or {}
    request = request.get('normalized') or request.get('raw') or {}
    contexts = document.get('context_evaluations', [])
    intents = request.get('intents') or list(dict.fromkeys(
        b['branch'] for c in contexts for b in c.get('branches', [])))
    counts = []
    for intent in intents:
        values = [b['status'] for c in contexts for b in c.get('branches', [])
                  if b['branch'] == intent]
        counts.append({'intent': intent, 'met': values.count('CRITERIA_MET'),
                       'not_met': values.count('CRITERIA_NOT_MET'),
                       'review': sum(value not in ('CRITERIA_MET', 'CRITERIA_NOT_MET') for value in values),
                       'unreported': len(contexts) - len(values)})
    findings = []
    for count in counts:
        if not contexts:
            text = 'No evaluated candidates are available for this check.'
        elif count['met']:
            text = 'Candidates meeting the duplication conditions were found.'
        elif count['review'] or count['unreported']:
            text = 'No confirmed match in the recorded results; some comparisons remain unresolved.'
        else:
            text = 'None of the evaluated candidates meet these duplication conditions.'
        findings.append({'intent': count['intent'], 'text': text})
    return {'target': request.get('target_name') or 'Unnamed target',
            'intents': intents, 'counts': counts, 'total': len(contexts),
            'findings': findings}


PURPOSE_LABELS = {'LINE': 'Spectral line', 'CONTINUUM': 'Continuum'}


def matching_contexts(document):
    """Select explicit positive context branches without recomputing any verdict."""
    intents = set(report_summary(document)['intents']) & set(PURPOSE_LABELS)
    return [(index, context) for index, context in enumerate(document.get('context_evaluations', []))
            if any(branch.get('branch') in intents and branch.get('status') == 'CRITERIA_MET'
                   for branch in context.get('branches', []))]

# Translate only explicit backend outcomes. These sentences never compute a verdict.
CONDITION_TEXT = {
    'POS-SINGLE': ('The position lies within the candidate half-power beam.',
                   'The position lies outside the candidate half-power beam.'),
    'ANGULAR': ('The angular resolutions meet the allowed comparison factor.',
                'The angular resolutions exceed the allowed comparison factor.'),
    'CONT-SETUP': ('The proposed setup meets the continuum qualification condition.',
                   'The proposed setup does not meet the continuum qualification condition.'),
    'CONT-FREQ': ('The representative frequencies meet the allowed comparison factor.',
                  'The representative frequencies exceed the allowed comparison factor.'),
    'CONT-RMS': ('The aggregate sensitivities meet the duplication condition.',
                 'The aggregate sensitivities do not meet the duplication condition.'),
    'LINE-FDM': ('Both windows have the required FDM mode evidence.',
                 'The FDM mode condition is not met for this pair.'),
    'LINE-COVERAGE': ('The requested sky frequency falls within this candidate window.',
                      'The requested sky frequency is outside this candidate window.'),
    'LINE-RESOLUTION-COMPATIBILITY': ('The spectral resolutions can be compared by the implemented method.',
                                     'The spectral resolutions are incompatible with the implemented comparison.'),
    'LINE-RMS': ('The sensitivities meet the condition after the recorded spectral and angular comparison.',
                 'The sensitivities do not meet the condition after the recorded spectral and angular comparison.'),
}
REASON_HELP = {
    'PLANNED_LINE_RMS_BASIS_UNRESOLVED': 'Clarify the planned line sensitivity basis and its spectral resolution.',
    'PROPOSED_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS': 'Enter the planned angular resolution for the sensitivity comparison.',
    'CANDIDATE_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS': 'Candidate angular resolution is unavailable; check the source metadata before interpreting sensitivity.',
    'UNIQUE_COMPONENT_10KMS_RMS_REQUIRED': 'The candidate window needs an unambiguous RMS at the documented reference resolution.',
    'CANDIDATE_BEAM_PROFILE_PROVISIONAL': 'The available beam interpretation is provisional. Review its evidence before using a formal result.',
    'MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED': 'Mosaic or unconfirmed geometry cannot be evaluated by the single-point method.',
    'QUEUE_GEOMETRY_UNSUPPORTED': 'This Queue geometry is outside the supported single-point method.',
    'TP_GEOMETRY_UNSUPPORTED': 'Total Power geometry is outside this comparison method.',
    'SPS_SELECTION_UNSUPPORTED': 'This observing setup is outside the implemented selection method.',
    'NONZERO_OFFSETS_NOT_APPLIED': 'Position offsets were not applied by this method; review the candidate position.',
    'PLANNED_LINE_RMS_REQUIRED': 'Enter the planned RMS for this proposed line.',
    'SOURCE_REDSHIFT_REQUIRED': 'Enter the source redshift to interpret the rest frequency.',
    'UNIQUE_WINDOW_LINE_SENSITIVITY_REQUIRED': 'Provide one unambiguous sensitivity requirement for this line window.',
    'UNIQUE_AGGREGATE_RMS_REQUIRED': 'Provide one unambiguous aggregate RMS requirement for the continuum setup.',
    'CONFLICTING_PLANNED_RESOLUTIONS': 'Resolve the conflicting planned spectral resolutions.',
    'NO_PROPOSED_LINE_WINDOWS': 'Add the frequency and requirements for at least one line of interest.',
    'PROPOSED_ENUMERATION_INCOMPLETE': 'Confirm a complete window list only if all proposed windows are included.',
    'ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED': 'The candidate resolution is coarser than requested; smoothing cannot supply the missing resolution.',
    'QUEUE_RESOLUTION_COARSER_THAN_PLANNED': 'The candidate resolution is coarser than requested; smoothing cannot supply the missing resolution.',
    'SOURCE_SPW_COMPONENT_UNASSIGNED': 'Candidate window evidence could not be linked unambiguously. Review the source record; do not borrow values from another window.',
    'CANDIDATE_MODE_EVIDENCE_REQUIRED': 'The candidate correlator mode is missing or unresolved. Check the candidate metadata.',
    'CONTINUUM_SETUP_DECLARATION_CONFLICT': 'The setup declaration conflicts with the complete window list. Check the declaration and bandwidths.',
    'METHOD_UNAPPROVED': 'This method is not approved for a formal result. Review the method record.',
    'ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED': 'Total Power scientific comparison is outside the implemented scope; review this candidate separately.',
    'UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED': 'The candidate array evidence does not establish a unique supported interferometric diameter.',
    'SINGLE_FIELD_CANDIDATE_REQUIRED': 'This comparison requires confirmed single-field candidate geometry.',
    'ARCHIVE_AQ_FAILED': 'Array evidence retrieval failed. Retain these candidates for review and retry the source acquisition when available.',
    'ARCHIVE_AQ_INCOMPLETE': 'Array evidence retrieval was incomplete. No partial array catalogue was used.',
}
GAP_CATEGORIES = {
    'USER_INPUT_MISSING': ('Proposed observation', 'Review the affected input and supply or clarify it if known.'),
    'ARCHIVE_EVIDENCE_MISSING': ('Archive evidence', 'Check the Archive metadata. Missing candidate values cannot be supplied by the proposed observation.'),
    'QUEUE_EVIDENCE_MISSING': ('Queue evidence', 'Check the supplied Queue file and its field definitions.'),
    'ASSOCIATION_UNRESOLVED': ('Window association', 'Review the source-to-window association before comparing values.'),
    'SCOPE_UNSUPPORTED': ('Unsupported comparison', 'This comparison needs a method outside the currently supported scope.'),
    'SOURCE_OR_SEARCH_INCOMPLETE': ('Source or retrieval', 'Review source availability and retrieval limits before interpreting the results.'),
    'METHOD_OR_DEPENDENCY': ('Comparison method', 'Review the method or its missing prerequisites; changing a requested value is not an automatic remedy.'),
    'UNCLASSIFIED': ('Further review', 'The report records an issue without a recognized explanation. Consult its technical record.'),
}


def criterion_explanation(record):
    reasons = list(record.get('reasons', [])) + [i['code'] for i in record.get('issues', [])]
    specific = list(dict.fromkeys(REASON_HELP[r] for r in reasons if r in REASON_HELP))
    if record.get('evaluation') == 'NOT_APPLICABLE':
        return 'This criterion does not apply within the recorded method scope.'
    if record.get('eligible_for_formal_aggregation') is False and record.get('outcome') is not None:
        return 'A value was calculated, but this criterion is not eligible for the formal result. Review the method and evidence.'
    if specific:
        return ' '.join(specific)
    texts = CONDITION_TEXT.get(record.get('criterion_id'))
    if texts and record.get('outcome') in ('SATISFIED', 'NOT_SATISFIED'):
        text = texts[record['outcome'] == 'NOT_SATISFIED']
        derived = dict(record.get('derived', []))
        if derived.get('factor') is not None and derived.get('max_factor') is not None:
            text += f" Recorded comparison factor: {display_number(derived['factor'])}; limit: {display_number(derived['max_factor'])}."
        return text
    if record.get('outcome') is not None:
        return 'The recorded outcome is shown, but an explanation for this criterion is not available. Consult the technical record.'
    return 'This report does not establish a result for this criterion. Review the missing information and technical record.'


def criterion_status(record):
    if record.get('evaluation') == 'NOT_APPLICABLE':
        return 'Not applicable'
    if record.get('eligible_for_formal_aggregation') is False:
        return 'Needs review'
    return {'SATISFIED': 'Condition met', 'NOT_SATISFIED': 'Condition not met'}.get(record.get('outcome'), 'Needs review')


def pair_title(pair):
    ref = (pair.get('attempt') or {}).get('reference') or {}
    association = ref.get('candidate_association') or {}
    spw = association.get('spw_token')
    if spw is None:
        spw = ref.get('spw_number')
    center = next((r.get('proposed') for r in pair.get('criteria', [])
                   if r.get('criterion_id') == 'LINE-COVERAGE'), None)
    requested = (f"Requested sky frequency {display_number(center['value'])} {center.get('unit') or ''}"
                 if center and center.get('value') is not None else 'Requested line')
    return f"{requested} / candidate window {spw if spw is not None else 'not identified'}"


def standalone_criteria(scope):
    """Avoid displaying identical common records twice in a LINE-only comparison."""
    records = scope.get('criteria', [])
    pairs = scope.get('line_pairs', [])
    if not pairs or any(b.get('branch') == 'CONTINUUM' for b in scope.get('branches', [])):
        return records
    return [r for r in records if not all(r in p.get('criteria', []) for p in pairs)]


def source_overview(document):
    result = []
    descriptions = {
        'COMPLETED': ('Retrieved', 'Retrieval completed within the recorded search scope.'),
        'FAILED': ('Unavailable', 'Retrieval failed. Available results from other sources remain usable within their scope.'),
        'INCOMPLETE': ('Incomplete', 'Only incomplete source evidence is available; this is not a complete search.'),
        'NOT_PROVIDED': ('Not configured', 'This source was selected but no source input was provided.'),
    }
    for name, source in document.get('sources', {}).items():
        if source.get('status') == 'NOT_SELECTED':
            continue
        label, message = descriptions.get(source.get('status'), ('Needs review', 'The recorded source status is not recognized.'))
        notes = [message]
        replay = source.get('replay') or {}
        if replay:
            if replay.get('fixture_kind') in {'SYNTHETIC_LINE_PAIRING_ACCEPTANCE', 'SYNTHETIC_NUMERIC_ACCEPTANCE'}:
                notes.insert(0, 'Reference example using synthetic data; this is not a current live Archive search.')
            else:
                notes.insert(0, 'Recorded Archive response; this run did not retrieve current Archive data.')
        aq = source.get('array_evidence') or {}
        acquisition = aq.get('acquisition') or {}
        aq_status = acquisition.get('status')
        if aq_status == 'FAILED':
            notes.append('Array evidence retrieval failed. Candidate array evidence remains unresolved.')
        elif aq_status == 'INCOMPLETE':
            notes.append('Array evidence retrieval was incomplete. No partial catalogue was used.')
        elif aq_status == 'COMPLETED' and aq.get('record_count') == 0:
            notes.append('The array lookup returned no records. This does not mean there is no duplication.')
        elif aq_status == 'SKIPPED':
            notes.append('No array lookup was performed for this run; see the recorded reason in technical records.')
        if source.get('requested_filters_fully_evaluated') is False and source.get('status') == 'COMPLETED':
            notes.append('Some requested retrieval filters could not be evaluated. Review the search limitations.')
        result.append({'name': 'Archive' if name == 'ARCHIVE' else 'Queue', 'label': label,
                       'attention': source.get('status') != 'COMPLETED' or aq_status in ('FAILED', 'INCOMPLETE')
                       or source.get('requested_filters_fully_evaluated') is False,
                       'notes': notes})
    return result


QUEUE_SCOPE_CODES = {
    'QUEUE_SINGLE_FIELD_REQUIRED', 'QUEUE_POSITION_SCOPE_UNRESOLVED',
    'QUEUE_CONTINUUM_SCOPE_UNSUPPORTED', 'BRANCH_SCOPE_UNSUPPORTED',
    'REGULAR_QUEUE_SETUP_REQUIRED', 'REGULAR_SPW_UNION_REQUIRED',
}


def queue_scope_help(context):
    """Explain recorded scope, without changing or recomputing any verdict."""
    if context.get('reference', {}).get('source') != 'QUEUE':
        return None
    criteria = list(context.get('criteria', []))
    for variant in context.get('beam_variants', []):
        criteria.extend(variant.get('criteria', []))
    geometry = {dict(c.get('details', [])).get('queue_geometry') for c in criteria}
    reasons = {r for c in criteria for r in c.get('reasons', [])}
    if 'CUSTOM_POINTING' in geometry:
        return ('QUEUE_CUSTOM', 'Custom mosaic pointings',
                'These Queue rows describe pointings in custom mosaics. The current method does not establish their single-point comparison scope; this is not a missing proposal input.')
    if 'RECTANGULAR_MOSAIC' in geometry:
        return ('QUEUE_RECTANGLE', 'Rectangular mosaics',
                'The current method does not evaluate rectangular mosaic coverage. These candidates remain unresolved.')
    if 'REGULAR_QUEUE_SETUP_REQUIRED' in reasons:
        return ('QUEUE_SCAN', 'Spectral scan configuration',
                'The current Queue workflow requires regular spectral windows. Spectral scans remain outside that workflow, including its shared position and angular-resolution scope.')
    if 'UNSPECIFIED_WITH_OFFSET' in geometry:
        return ('QUEUE_OFFSET', 'Blank Mosaic with coordinate offsets',
                'This report records unresolved geometry for a blank Mosaic value with offsets. A new assessment can use the documented blank-Mosaic interpretation; existing results are unchanged.')
    return None


def attention_groups(document, inspection):
    """Group existing inspection occurrences; counts are never observation verdicts."""
    contexts = document.get('context_evaluations', [])
    indices = {c['context_id']: i for i, c in enumerate(contexts)}
    scope_help = {c['context_id']: queue_scope_help(c) for c in contexts}
    groups = {}
    for gap in inspection.get('gap_occurrences', []):
        category = gap.get('category', 'UNCLASSIFIED')
        title, fallback = GAP_CATEGORIES.get(category, GAP_CATEGORIES['UNCLASSIFIED'])
        help_text = scope_help.get(gap.get('context_id')) if gap['code'] in QUEUE_SCOPE_CODES else None
        if help_text:
            category, title, fallback = help_text
        group = groups.setdefault(category, {'title': title, 'count': 0, 'messages': [], 'candidates': []})
        group['count'] += 1
        # Unknown reason codes do not inherit user-input advice from a category.
        message = fallback if help_text else REASON_HELP.get(gap['code'], fallback if category != 'USER_INPUT_MISSING'
                                  else 'The report identifies a proposed-input issue. Review the input diagnostics in technical records.')
        if message not in group['messages']:
            group['messages'].append(message)
        index = indices.get(gap.get('context_id'))
        if index is not None and index not in group['candidates']:
            group['candidates'].append(index)
    return list(groups.values())
