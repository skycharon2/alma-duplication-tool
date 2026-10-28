"""Read-only presentation index for Archive Mosaic assessment reports.

Candidate categories describe recorded branch results. They are not independent
scientific decisions and do not establish search-wide duplication or absence.
"""

from collections import Counter


MOSAIC_REPORT_SCHEMAS = {'archive_mosaic_backend_2', 'submitted_line_mosaic_search_report_1'}

PROJECTION_VERSION = 'mosaic_browser_view_1'
BUCKETS = ('MATCH', 'NOT_MET', 'NEEDS_REVIEW', 'UNAVAILABLE')
BRANCH_STATUSES = ('CRITERIA_MET', 'CRITERIA_NOT_MET', 'INDETERMINATE')


def _criterion(record):
    """Keep identifiers and recorded results, not operands or calculations."""
    return {
        'criterion_id': record.get('criterion_id'),
        'outcome': record.get('outcome'),
        'eligible_for_formal_aggregation': record.get('eligible_for_formal_aggregation'),
    }


def _context(record, index):
    branches = [
        {'branch': branch.get('branch'), 'status': branch.get('status')}
        for branch in record.get('branches', ())
    ]
    pairs = record.get('line_pairs') or ()
    pair_statuses = Counter(pair.get('status') or 'UNRECORDED' for pair in pairs)
    return {
        'context_index': index,
        'context_id': record.get('context_id'),
        'branches': branches,
        'criteria': [_criterion(item) for item in record.get('criteria', ())],
        'request_criteria': [
            _criterion(item) for item in record.get('request_criteria', ())
        ],
        'line_pair_count': len(pairs),
        'line_pair_status_counts': dict(sorted(pair_statuses.items())),
    }


def _bucket(candidate_status, branch_statuses):
    """Categorize for navigation; only the backend assigns scientific statuses."""
    if candidate_status != 'EVALUATED':
        return 'UNAVAILABLE'
    if 'CRITERIA_MET' in branch_statuses:
        return 'MATCH'
    if branch_statuses and all(
        status == 'CRITERIA_NOT_MET' for status in branch_statuses
    ):
        return 'NOT_MET'
    return 'NEEDS_REVIEW'


def mosaic_report_projection(document):
    """Build a bounded-in-content, one-entry-per-candidate display index.

    Existing candidate order, context order, duplicated identities and the
    publication bytes remain untouched. This index contains no region polygons,
    pointing rows, full metadata, spectral operands or calculation records.
    """
    if document.get('schema_version') not in MOSAIC_REPORT_SCHEMAS:
        raise ValueError('Expected Archive Mosaic backend report v2')

    candidates = []
    bucket_counts = Counter()
    branch_counts = Counter()
    source_status_counts = Counter()
    context_count = 0
    for candidate_index, candidate in enumerate(document['candidates']):
        candidate_status = candidate.get('status')
        source_status_counts[candidate_status or 'UNRECORDED'] += 1
        contexts = [
            _context(record, index)
            for index, record in enumerate((candidate.get('evaluation') or {}).get('contexts', ()))
        ]
        context_count += len(contexts)
        statuses = [
            branch['status'] for context in contexts for branch in context['branches']
        ]
        if candidate_status == 'EVALUATED':
            branch_counts.update(status or 'UNRECORDED' for status in statuses)
        bucket = _bucket(candidate_status, statuses)
        bucket_counts[bucket] += 1
        candidates.append({
            'candidate_index': candidate_index,
            'member_ous_uid': candidate.get('member_ous_uid'),
            'source_name': candidate.get('source_name'),
            'status': candidate_status,
            'metadata_status': candidate.get('metadata_status'),
            'bucket': bucket,
            'context_count': len(contexts),
            'contexts': contexts,
        })

    overview = {
        'candidate_count': len(candidates),
        'context_count': context_count,
        'candidate_buckets': {name: bucket_counts[name] for name in BUCKETS},
        'branch_status_counts': {
            **{name: branch_counts[name] for name in BRANCH_STATUSES},
            'OTHER_OR_UNRECORDED': sum(
                count for name, count in branch_counts.items()
                if name not in BRANCH_STATUSES
            ),
        },
        'candidate_source_status_counts': dict(sorted(source_status_counts.items())),
    }
    return {
        'mosaic': True,
        'projection_schema_version': PROJECTION_VERSION,
        'summary': {'target': document['proposed']['source_name']},
        'document': {
            'proposed': {
                name: document['proposed'][name] for name in ('source_name', 'row_count')
            },
            'assessment_status': document['assessment_status'],
            'discovery': {'status': document['discovery']['status']},
        },
        'candidate_count': len(candidates),
        'mosaic_overview': overview,
        'candidate_summaries': candidates,
    }
