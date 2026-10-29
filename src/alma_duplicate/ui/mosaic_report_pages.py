"""Read-only Archive Mosaic Member navigation over the saved presentation index.

Matching selects *Members* with at least one recorded matching candidate. Every
candidate identity and every context stored for those Members remains accessible.
Neither grouping nor page selection assigns or changes scientific outcomes.
"""

from collections import OrderedDict

from alma_duplicate.ui.mosaic_report_view import PROJECTION_VERSION

PAGE_SIZE = 20
MOSAIC_VIEWS = ('all', 'matching', 'review', 'not_met')


def _member_key(summary, index):
    """Only an exact recorded Member UID can join candidate identities."""
    member = summary.get('member_ous_uid')
    return ('member', member) if isinstance(member, str) and member else ('candidate', index)


def _unique(values):
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def _candidate_identity(candidate):
    """Project/Group/Execution identities only from matching saved metadata rows."""
    member, target = candidate.get('member_ous_uid'), candidate.get('source_name')
    rows = [row for row in (candidate.get('metadata_rows') or ())
            if isinstance(row, dict) and row.get('member_ous_uid') == member
            and row.get('target_name') == target]
    return {
        'projects': _unique(row.get('proposal_id') for row in rows),
        'group_ous_uids': _unique(row.get('group_ous_uid') for row in rows),
        'asdm_uids': _unique(row.get('asdm_uid') for row in rows),
    }


def _context_identity(context, member, target):
    """Read per-context SPW and ASDM IDs from explicit LINE pair associations.

    A raw Archive row's execution is not automatically assigned to every
    context; the association must explicitly agree with Member and target.
    """
    spws, executions = [], []
    stored = context.get('display_identity') or {}
    recorded_member = stored.get('Member OUS', stored.get('member_ous_uid'))
    recorded_target = stored.get('Target', stored.get('target_name'))
    if recorded_member == member and recorded_target == target:
        if stored.get('ASDM'):
            executions.append(stored['ASDM'])
        if stored.get('SPW') is not None:
            spws.append(str(stored['SPW']))
    for pair in context.get('line_pairs') or ():
        reference = ((pair.get('attempt') or {}).get('reference') or {})
        association = reference.get('candidate_association') or {}
        identity = association.get('context') or {}
        if identity.get('member_ous_uid') != member or identity.get('source_name') != target:
            continue
        token = association.get('spw_token')
        if token is not None and str(token).strip():
            spws.append(str(token))
        asdm = identity.get('asdm_uid')
        if isinstance(asdm, str) and asdm:
            executions.append(asdm)
    return {'spws': _unique(spws), 'asdm_uids': _unique(executions)}


def _line_presentations(candidate, context):
    """Label stored pairs by submitted order, never by matching order."""
    raw = ((candidate.get('evaluation') or {}).get('request') or {}).get('raw') or {}
    requirements = raw.get('line_requirements') or []
    by_id = {r.get('requirement_id'): (i + 1, r) for i, r in enumerate(requirements)}
    result = []
    for pair in context.get('line_pairs') or []:
        attempt = pair.get('attempt') or {}
        identifier = attempt.get('proposed_window_id') or (attempt.get('reference') or {}).get('proposed_window_id')
        number, requirement = by_id.get(identifier, (None, {}))
        fields = []
        for label, key in [('Input frequency', 'window_center'),
                           ('Spectral resolution', 'spectral_resolution'), ('RMS', 'rms')]:
            quantity = requirement.get(key) or {}
            if quantity.get('value') is not None:
                fields.append((label, ' '.join(str(quantity[k]) for k in ('value', 'unit', 'kind')
                                              if quantity.get(k) is not None)))
        z = requirement.get('source_redshift', raw.get('source_redshift'))
        if z is not None:
            fields.append(('Redshift z', str(z)))
        if requirement.get('correlator_mode'):
            fields.append(('Mode', requirement['correlator_mode']))
        result.append({'pair': pair, 'label': f'LINE requirement {number}' if number else
                       f'LINE requirement {identifier}' if identifier else 'LINE pair',
                       'fields': fields})
    matches = [item for item in result if item['pair'].get('status') == 'CRITERIA_MET']
    others = [item for item in result if item['pair'].get('status') != 'CRITERIA_MET']
    return matches[:10] + others[:10]


def _candidate_entry(index, summary, candidate):
    if summary.get('candidate_index') != index:
        raise ValueError('Mosaic candidate index identity mismatch')
    if (candidate.get('member_ous_uid') != summary.get('member_ous_uid')
            or candidate.get('source_name') != summary.get('source_name')):
        raise ValueError('Mosaic candidate payload identity mismatch')
    contexts = []
    for context_index, context in enumerate((candidate.get('evaluation') or {}).get('contexts') or ()):
        matching = any(branch.get('status') == 'CRITERIA_MET'
                       for branch in context.get('branches') or ())
        contexts.append({
            'index': context_index, 'record': context, 'matching': matching,
            'line_presentations': _line_presentations(candidate, context),
            **_context_identity(context, candidate.get('member_ous_uid'), candidate.get('source_name')),
        })
    # Matching first in presentation only. Recorded Context numbers never change.
    contexts.sort(key=lambda item: not item['matching'])
    # Match Single Pointing: join only a unique recorded execution identity.
    children = OrderedDict()
    for item in contexts:
        execution = item['asdm_uids'][0] if len(item['asdm_uids']) == 1 else None
        key = ('execution', execution) if execution else ('context', item['index'])
        children.setdefault(key, {'execution': execution, 'contexts': []})['contexts'].append(item)
    return {
        'children': list(children.values()),
        'candidate_index': index, 'candidate': candidate, 'summary': summary,
        'identity': _candidate_identity(candidate), 'contexts': contexts,
    }


def mosaic_report_page(projection, page, view, load_candidate):
    """Select report pages without reassessing criteria or modifying raw exports.

    In ``matching`` view pages contain up to 20 complete *Member groups*. This
    can mean more than 20 candidate identities when a Member has many targets.
    Other diagnostic views retain their historical candidate-level pagination.
    """
    if projection.get('projection_schema_version') != PROJECTION_VERSION:
        raise ValueError('Unsupported Mosaic browser projection version')
    if type(page) is not int or page < 1 or view not in (*MOSAIC_VIEWS, 'matches'):
        raise ValueError('Invalid Mosaic report page selection')
    selected_view = 'matching' if view == 'matches' else view
    summaries = projection['candidate_summaries']
    if len(summaries) != projection['candidate_count']:
        raise ValueError('Mosaic candidate index length mismatch')

    def visible(summary):
        bucket = summary['bucket']
        return (selected_view == 'all'
                or (selected_view == 'matching' and bucket == 'MATCH')
                or (selected_view == 'review' and bucket in ('NEEDS_REVIEW', 'UNAVAILABLE'))
                or (selected_view == 'not_met' and bucket == 'NOT_MET'))

    if selected_view == 'matching':
        by_member = OrderedDict()
        matching_members = set()
        for index, summary in enumerate(summaries):
            if summary.get('candidate_index') != index:
                raise ValueError('Mosaic candidate index identity mismatch')
            key = _member_key(summary, index)
            by_member.setdefault(key, []).append(index)
            if summary['bucket'] == 'MATCH':
                matching_members.add(key)
        selected_keys = [key for key in by_member if key in matching_members]
        member_count = len(selected_keys)
        visible_count = sum(len(by_member[key]) for key in selected_keys)
        pages = max(1, (member_count + PAGE_SIZE - 1) // PAGE_SIZE)
        if page > pages:
            raise IndexError('Mosaic report page unavailable')
        keys_on_page = selected_keys[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        indexes = [index for key in keys_on_page for index in by_member[key]]
        # Do not split one Member between pages, even when it has many targets.
    else:
        selected = [index for index, summary in enumerate(summaries) if visible(summary)]
        visible_count = len(selected)
        pages = max(1, (visible_count + PAGE_SIZE - 1) // PAGE_SIZE)
        if page > pages:
            raise IndexError('Mosaic report page unavailable')
        indexes = selected[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        member_count = None

    entries, groups, group_by_member = [], [], {}
    for index in indexes:
        summary = summaries[index]
        entry = _candidate_entry(index, summary, load_candidate(index))
        entries.append(entry)
        key = _member_key(summary, index)
        if key not in group_by_member:
            group = {'member_ous_uid': summary.get('member_ous_uid'),
                     'anchor': f'mosaic-member-{index}', 'entries': [],
                     'projects': [], 'group_ous_uids': [], 'has_matching_candidate': False}
            group_by_member[key] = group
            groups.append(group)
        group = group_by_member[key]
        group['entries'].append(entry)
        group['has_matching_candidate'] |= summary['bucket'] == 'MATCH'
        for field in ('projects', 'group_ous_uids'):
            for item in entry['identity'][field]:
                if item not in group[field]:
                    group[field].append(item)

    return {
        'mosaic': True,
        'document': projection['document'],
        'candidate_count': projection['candidate_count'],
        'candidate_summaries': [entry['summary'] for entry in entries],
        'candidates': [entry['candidate'] for entry in entries],
        'candidate_entries': entries,
        'member_groups': groups,
        'matching_member_count': member_count,
        'mosaic_overview': projection['mosaic_overview'],
        'result_view': selected_view,
        'visible_count': visible_count,
        'page': page, 'pages': pages,
    }
