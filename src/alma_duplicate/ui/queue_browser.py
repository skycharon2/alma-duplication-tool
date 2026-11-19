"""Browser adapters over the existing Queue scientific evaluators."""
from dataclasses import replace
from threading import Lock
from alma_duplicate.assessment import AssessmentOptions, AssessmentSources
from alma_duplicate.reporting import json_value
from alma_duplicate.request_validation import validate_proposed_observation


def memoized_loader(loader):
    """Cache a snapshot or its acquisition error for one submission."""
    if loader is None:
        return None
    loaded, result, error = False, None, None
    lock = Lock()

    def load():
        nonlocal loaded, result, error
        with lock:
            if not loaded:
                try:
                    result = loader()
                except (OSError, ValueError) as exc:
                    error = exc
                loaded = True
        if error is not None:
            raise error
        return result
    return load


def assess_geometry(document, loader, proposed=None):
    prepared = None
    raw = document['request']
    if raw.get('line_input_contract'):
        from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
        prepared = prepare_submitted_line_request(raw)
        request = prepared.line_request
        raw = json_value(request.raw_input)
    search = document['search_options'] | {'sources': ['QUEUE']}
    validation = validate_proposed_observation(raw, search)
    if not validation.is_valid:
        raise ValueError('Invalid browser Queue geometry request')
    if prepared is not None:
        validation = replace(validation, request=request)
    kwargs = dict(options=AssessmentOptions(), sources=AssessmentSources(queue_loader=loader),
                  input_sha256=None, report_detail='full', prepared=prepared)
    if proposed is None:
        from alma_duplicate.queue_single_mosaic_assessment import assess_single_mosaics
        result = assess_single_mosaics(validation, **kwargs)
    else:
        from alma_duplicate.queue_mosaic_assessment import assess_queue_mosaic
        result = assess_queue_mosaic(validation, proposed, **kwargs)
    result.document['scientific_request'] = json_value(document['request'])
    return result


def candidate_scope_help(candidate):
    """Explain retained spectral limitations without inferring a new verdict."""
    from alma_duplicate.ui.report_view import queue_spectral_scope_help
    science = candidate.get('science') or {}
    reasons = []
    for scope in [science, *science.get('variants', [])]:
        for record in [*scope.get('criteria', []), *scope.get('branches', [])]:
            reasons.extend(record.get('reasons') or [])
    return queue_spectral_scope_help(reasons)


def presentation(report):
    """Flatten only presentation; keep candidates and array evidence independent."""
    result = []
    for kind, geometry in report.get('geometry_reports', {}).items():
        for candidate in geometry.get('candidates', []):
            group = candidate.get('group') or {}
            result.append(dict(kind=kind, candidate=candidate,
                scope_help=candidate_scope_help(candidate),
                target=group.get('target_name', 'Queue candidate'),
                project=group.get('project_code', 'Not recorded')))
    return result


def result_bucket(candidate):
    truths = [b.get('truth') for b in candidate.get('science', {}).get('branches', [])]
    return ('matching' if 'TRUE' in truths else 'not_met'
            if truths and all(t == 'FALSE' for t in truths) else 'review')


def report_header(report):
    """Small retained summary, excluding point relations and scientific operands."""
    from collections import Counter
    counts = Counter(result_bucket(e['candidate']) for e in presentation(report))
    header = {k: v for k, v in report.items() if k not in {'geometry_reports', 'inventory'}}
    inventory = report.get('inventory') or {}
    header['inventory'] = {k: v for k, v in inventory.items() if k != 'source_rows'}
    if 'source_rows' in inventory:
        limitations = Counter()
        outside_by_geometry = Counter()
        for row in inventory['source_rows']:
            codes = set(row.get('limitations', []))
            limitations.update(codes)
            if 'OUTSIDE_SINGLE_TO_MOSAIC_SCOPE' in codes:
                outside_by_geometry[row.get('geometry_kind') or 'UNKNOWN'] += 1
        header['inventory']['limitation_row_counts'] = dict(sorted(limitations.items()))
        header['inventory']['outside_scope_by_geometry'] = dict(sorted(outside_by_geometry.items()))
    header['candidate_counts'] = {k: counts[k] for k in ('matching', 'review', 'not_met')}
    # Count the full candidate inventory before report pagination. An intent is
    # counted once per configuration, even if an old record repeats branches.
    intent_counts = {}
    for entry in presentation(report):
        by_intent = {}
        for branch in entry['candidate'].get('science', {}).get('branches', []):
            intent = branch.get('branch')
            if intent not in {'CONTINUUM', 'LINE'}:
                continue
            by_intent.setdefault(intent, set()).add(branch.get('truth'))
        for intent, truths in by_intent.items():
            bucket = ('matching' if 'TRUE' in truths else 'not_met'
                      if truths == {'FALSE'} else 'review')
            intent_counts.setdefault(intent, {'matching': 0, 'review': 0, 'not_met': 0})[bucket] += 1
    header['candidate_counts_by_intent'] = intent_counts
    header['intent_counts_scope'] = 'ALL_STORED_CANDIDATE_CONFIGURATIONS'
    header['geometry_reports'] = {}
    return header


def displayed_candidate_limitations(candidate):
    return [limitation for limitation in candidate.get('limitations') or []
            if limitation.get('code') not in {
                'GALACTIC_OFFSET_MODEL_NOT_OT_VALIDATED', 'GALACTIC_GRID_MODEL_NOT_OT_VALIDATED',
            }]


def ownership_notice_groups(candidates):
    """Deduplicate identical notices within one object, never its scientific results."""
    import json
    groups = {}
    for candidate in candidates:
        ownership = candidate.get('pointing_ownership') or {}
        limitations = displayed_candidate_limitations(candidate)
        if not limitations and not ownership.get('unassessed_arrays'):
            continue
        identity = candidate.get('group') or {}
        project, target = identity.get('project_code'), identity.get('target_name')
        # Missing object identities never authorize grouping unrelated records.
        scope = (project, target) if project and target else ('candidate', candidate.get('candidate_id', id(candidate)))
        key = (scope, json.dumps([ownership, limitations], sort_keys=True))
        group = groups.setdefault(key, dict(project=project or 'Not recorded', target=target or 'Queue candidate',
                                           candidate=dict(candidate, limitations=limitations), count=0))
        group['count'] += 1
    return list(groups.values())
