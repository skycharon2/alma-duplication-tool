"""Select Archive Mosaic report pages from the stored presentation index.

The page projection never evaluates a rule. It indexes previously recorded
candidate categories and reads only the selected original candidate payloads.
"""

from alma_duplicate.ui.mosaic_report_view import PROJECTION_VERSION

PAGE_SIZE = 20
MOSAIC_VIEWS = ('all', 'matching', 'review', 'not_met')


def mosaic_report_page(projection, page, view, load_candidate):
    """Return a read-only page of candidate records and Member presentation groups.

    The shared ``matches`` default selects matching Mosaic candidates.
    Explicit ``all`` retains the complete original candidate list. A matching category means at least one recorded
    matching branch, not a verdict for an entire Member OUS.
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

    indexes = [index for index, entry in enumerate(summaries) if visible(entry)]
    pages = max(1, (len(indexes) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > pages:
        raise IndexError('Mosaic report page unavailable')
    on_page = indexes[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
    entries, groups, group_by_member = [], [], {}
    for index in on_page:
        summary = summaries[index]
        if summary['candidate_index'] != index:
            raise ValueError('Mosaic candidate index identity mismatch')
        item = {'candidate_index': index, 'candidate': load_candidate(index),
                'summary': summary}
        entries.append(item)
        # An absent Member identity is not evidence that two records belong
        # together. Keep those records as separate groups.
        member = summary.get('member_ous_uid')
        key = ('member', member) if member else ('candidate', index)
        if key not in group_by_member:
            group = {'member_ous_uid': member, 'anchor': f'mosaic-member-{index}',
                     'entries': []}
            group_by_member[key] = group
            groups.append(group)
        group_by_member[key]['entries'].append(item)

    return {
        'mosaic': True,
        'document': projection['document'],
        'candidate_count': projection['candidate_count'],
        'candidate_summaries': [entry['summary'] for entry in entries],
        'candidates': [entry['candidate'] for entry in entries],
        'candidate_entries': entries,
        'member_groups': groups,
        'mosaic_overview': projection['mosaic_overview'],
        'result_view': selected_view,
        'visible_count': len(indexes),
        'page': page, 'pages': pages,
    }
