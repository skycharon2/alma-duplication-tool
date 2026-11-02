"""Read-only, candidate-indexed presentation for Queue Custom reports."""
from collections import Counter

SCHEMA = 'queue_custom_assessment_1'
PAGE_SIZE = 20
LABELS = {'TRUE': 'Criteria met', 'FALSE': 'Criteria not met', 'UNKNOWN': 'Information insufficient',
          'SATISFIED': 'Satisfied', 'NOT_SATISFIED': 'Not satisfied'}


def projection(document):
    from alma_duplicate.queue_custom_science import custom_object_results
    objects = document.get('object_results')
    if objects is None:
        objects = custom_object_results(document['candidates'])
    offsets = {c['candidate_id']: i for i, c in enumerate(document['candidates'])}
    summaries = []
    for obj in objects:
        truths = obj['truth_by_intent'].values()
        bucket = ('matching' if 'TRUE' in truths else 'not_met'
                  if truths and all(t == 'FALSE' for t in truths) else 'review')
        summaries.append(dict(**obj, indices=[offsets[cid] for cid in obj['candidate_ids']], bucket=bucket))
    summaries.sort(key=lambda obj: (obj['project_code'], obj['target_name']))
    counts = Counter(s['bucket'] for s in summaries)
    header = {k: document.get(k) for k in ('assessment_status', 'sources', 'profile', 'model_status',
        'operational_columns', 'summary', 'request_criteria', 'scientific_request', 'snapshot_sha256', 'source_as_of')}
    header['exclusion_counts'] = dict(
        mosaic=len(document.get('excluded_mosaic_candidates', [])),
        non_mosaic=len(document.get('excluded_non_mosaic_rows', [])))
    return dict(queue_custom=True, summary={'target': document['proposed']['source_name']},
                document=header, candidate_summaries=summaries,
                counts={key: counts[key] for key in ('matching', 'review', 'not_met')})


def report_page(index, page, view, load_candidate):
    view = 'matching' if view == 'matches' else view
    if type(page) is not int or page < 1 or view not in ('matching', 'all', 'review', 'not_met'):
        raise IndexError('Invalid Queue Custom report page')
    visible = [s for s in index['candidate_summaries'] if view == 'all' or s['bucket'] == view]
    pages = max(1, (len(visible) + PAGE_SIZE - 1)//PAGE_SIZE)
    if page > pages:
        raise IndexError('Queue Custom report page unavailable')
    candidates = []
    for s in visible[(page-1)*PAGE_SIZE:page*PAGE_SIZE]:
        setups = [load_candidate(i) for i in s['indices']]
        if [c['candidate_id'] for c in setups] != s['candidate_ids']:
            raise ValueError('Queue Custom report candidate identity mismatch')
        setups.sort(key=lambda c: c['source_rows'][0]['physical_lines'][0])
        for c in setups:
            columns = index['document'].get('operational_columns') or []
            row = dict(zip(columns, c['source_rows'][0]['raw_values']))
            c['settings'] = row
            c['spws'] = []
            for number in range(1, 17):
                values = [row.get(f'{field} SPW {number}', '') for field in
                          ('Freq', 'Bandwidth', 'Spec.Res.')]
                if any(value.strip() for value in values):
                    c['spws'].append((number, *values))
            c['display_spws'] = len(c['spws'])
            c['display_resolution'] = row.get('Req. Ang. Res.')
            for pointing in c['source_rows']:
                coordinates = dict(zip(columns, pointing['raw_values']))
                pointing['offsets'] = [coordinates.get(field) for field in ('Long Offset', 'Lat Offset')]
        candidates.append(dict(**s, setups=setups))
    return dict(queue_custom=True, document=index['document'], counts=index['counts'],
        candidates=candidates, target=index['summary']['target'],
        page=page, pages=pages, result_view=view, visible_count=len(visible), labels=LABELS)
