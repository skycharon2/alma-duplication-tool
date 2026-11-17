"""Pure pagination shared by temporary and persistent Queue report readers."""
from copy import deepcopy
import math


def queue_saved_page(projection, page, view, load_candidate):
    view = 'matching' if view == 'matches' else view
    index = projection['queue_index']
    if view not in {'matching', 'all', 'review', 'not_met'}:
        raise IndexError('Invalid Queue view')
    visible = [e for e in index['entries'] if view == 'all' or e['bucket'] == view]
    pages = max(1, math.ceil(len(visible) / 20))
    if type(page) is not int or page < 1 or page > pages:
        raise IndexError('Queue report page unavailable')
    document = deepcopy(index['header'])
    for entry in visible[(page - 1) * 20:page * 20]:
        document['geometry_reports'].setdefault(entry['kind'], {'candidates': []})['candidates'].append(
            load_candidate(entry))
    return dict(unified_queue=True, document=document, page=page, pages=pages,
                result_view=view, visible_count=len(visible))
