"""Presentation indexes and page selection over unchanged report contexts."""

from copy import deepcopy

from alma_duplicate.ui.report_view import (
    attention_groups, matching_contexts, member_groups, report_summary, source_overview,
)


def report_projection(document, inspection, *, compact=False):
    """Index exact recorded matches and identities, without deriving new verdicts."""
    matches = matching_contexts(document)
    groups = member_groups(matches)
    for group in groups:
        group['entries'] = [index for index, _ in group['entries']]
        for child in group['children']:
            child['entries'] = [index for index, _ in child['entries']]
    metadata = {key: value for key, value in document.items() if key != 'context_evaluations'}
    if compact:
        # Per-row retrieval evidence is retained in the complete original download.
        metadata['sources'] = {
            name: {key: value for key, value in source.items()
                   if key not in {'rows', 'omitted_candidate_ids'}}
            for name, source in document['sources'].items()
        }
    return {
        'document': metadata, 'summary': report_summary(document),
        'source_overview': source_overview(document),
        'attention': attention_groups(document, inspection),
        'groups': groups, 'match_count': len(matches),
        'total': len(document['context_evaluations']),
    }


def report_page(projection, page, view, load_context):
    """Read only the contexts selected by a complete-Member or audit page."""
    if view not in {'matches', 'all'} or type(page) is not int or page < 1:
        raise ValueError('Invalid report page')
    groups = projection['groups']
    count = projection['total'] if view == 'all' else len(groups)
    pages = max(1, (count + 19) // 20)
    if page > pages:
        raise IndexError('Report page unavailable')
    start = (page - 1) * 20
    page_groups = deepcopy(groups[start:start + 20]) if view == 'matches' else []
    indices = (list(range(start, min(start + 20, count))) if view == 'all' else
               [index for group in page_groups for child in group['children'] for index in child['entries']])
    contexts = {index: load_context(index) for index in indices}
    for group in page_groups:
        for child in group['children']:
            child['entries'] = [(index, contexts[index]) for index in child['entries']]
    return {
        'document': projection['document'], 'summary': projection['summary'],
        'source_overview': projection['source_overview'], 'attention': projection['attention'],
        'contexts': [contexts[index] for index in indices], 'context_indices': indices,
        'member_groups': page_groups, 'group_count': len(groups),
        'member_count': sum(g['member'] is not None for g in groups),
        'queue_count': sum(g['source'] == 'QUEUE' for g in groups),
        'ungrouped_count': sum(g['source'] != 'QUEUE' and g['member'] is None for g in groups),
        'result_view': view, 'visible_count': projection['total'] if view == 'all' else projection['match_count'],
        'match_count': projection['match_count'], 'page': page, 'pages': pages,
    }
