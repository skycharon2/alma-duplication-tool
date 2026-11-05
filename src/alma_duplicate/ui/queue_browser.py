"""Browser adapters over the existing Queue scientific evaluators."""
from dataclasses import replace
from alma_duplicate.assessment import AssessmentOptions, AssessmentSources
from alma_duplicate.reporting import json_value
from alma_duplicate.request_validation import validate_proposed_observation


def memoized_loader(loader):
    """Cache a snapshot or its acquisition error for one submission."""
    if loader is None:
        return None
    loaded, result, error = False, None, None

    def load():
        nonlocal loaded, result, error
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


def presentation(report):
    """Flatten only presentation; keep candidates and array evidence independent."""
    result = []
    for kind, geometry in report.get('geometry_reports', {}).items():
        for candidate in geometry.get('candidates', []):
            group = candidate.get('group') or {}
            result.append(dict(kind=kind, candidate=candidate,
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
