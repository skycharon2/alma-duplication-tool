"""Pure pagination shared by temporary and persistent Queue report readers."""
from copy import deepcopy
import math


def queue_saved_index(index, load_candidate):
    """Apply current coverage exclusions to saved indexes from older runs."""
    if index['header'].get('aca_coverage_only_filtered'):
        return index['header'], index['entries']
    from alma_duplicate.ui.queue_browser import result_bucket

    document = deepcopy(index['header'])
    entries = []
    for entry in index['entries']:
        if entry['bucket'] in {'review', 'matching'}:
            candidate = load_candidate(entry)
            for intent, counts in document.get('candidate_counts_by_intent', {}).items():
                if result_bucket(candidate, intent) == 'coverage_only':
                    counts['review'] -= 1
            if result_bucket(candidate) == 'coverage_only':
                document['candidate_counts']['review'] -= 1
                continue
        entries.append(entry)
    return document, entries


def queue_saved_page(projection, page, view, load_candidate):
    view = 'matching' if view == 'matches' else view
    if view not in {'matching', 'all', 'review', 'not_met'}:
        raise IndexError('Invalid Queue view')
    header, entries = queue_saved_index(projection['queue_index'], load_candidate)
    document = deepcopy(header)
    visible = [e for e in entries
               if e['bucket'] != 'coverage_only' and (view == 'all' or e['bucket'] == view)]
    pages = max(1, math.ceil(len(visible) / 20))
    if type(page) is not int or page < 1 or page > pages:
        raise IndexError('Queue report page unavailable')
    for entry in visible[(page - 1) * 20:page * 20]:
        document['geometry_reports'].setdefault(entry['kind'], {'candidates': []})['candidates'].append(
            load_candidate(entry))
    return dict(unified_queue=True, document=document, page=page, pages=pages,
                result_view=view, visible_count=len(visible))
