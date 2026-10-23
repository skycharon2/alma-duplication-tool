"""Conservative candidate groups of execution-local reported field centres."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json

from alma_duplicate.archive_mosaic_pointings import (
    MAX_PAIR_DISTANCES, compare_pointings, separation_arcsec,
)


def group_pointings(executions: list[dict], *, tolerance_arcsec: float):
    """Reject ambiguous connected components instead of choosing a partition.

    Every input field appears exactly once, including unmatched and ambiguous
    components. No representative, averaged position or physical identity is inferred.
    """
    comparison = compare_pointings(executions, tolerance_arcsec=tolerance_arcsec)
    fields = {(f['asdm_uid'], f['field_id']): f for f in comparison['fields']}
    adjacency = {key: set() for key in fields}
    for pair in comparison['pairs']:
        for field in pair['left_fields']:
            left = (pair['left_asdm_uid'], field['field_id'])
            for field_id in field['within_tolerance_field_ids']:
                right = (pair['right_asdm_uid'], field_id)
                adjacency[left].add(right)
                adjacency[right].add(left)
    components = []
    visited = set()
    for start in sorted(fields):
        if start in visited:
            continue
        stack, component = [start], []
        visited.add(start)
        while stack:
            key = stack.pop()
            component.append(key)
            for neighbour in sorted(adjacency[key]):
                if neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(component))
    if sum(len(c) * (len(c) - 1) // 2 for c in components) > MAX_PAIR_DISTANCES:
        raise ValueError('Group diameter comparison budget exceeded')
    expected = sorted(e['asdm_uid'] for e in executions)
    groups = []
    for component in components:
        counts = Counter(uid for uid, _ in component)
        duplicate_executions = sorted(uid for uid, count in counts.items() if count > 1)
        diameter = 0.0
        outside = []
        for left, right in combinations(component, 2):
            distance = separation_arcsec(fields[left], fields[right])
            diameter = max(diameter, distance)
            if distance > tolerance_arcsec:
                outside.append(dict(left=dict(asdm_uid=left[0], field_id=left[1]),
                                    right=dict(asdm_uid=right[0], field_id=right[1]),
                                    separation_arcsec=distance))
        reasons = []
        if duplicate_executions:
            reasons.append('MULTIPLE_FIELDS_FROM_SAME_EXECUTION')
        if outside:
            reasons.append('NON_TRANSITIVE_TOLERANCE_CHAIN')
        missing = sorted(set(expected) - set(counts))
        status = ('AMBIGUOUS' if reasons else 'UNMATCHED' if len(component) == 1 else
                  'CANDIDATE_PARTIAL' if missing else 'CANDIDATE_FULL')
        identity = json.dumps(component, separators=(',', ':')).encode()
        groups.append(dict(group_id=sha256(identity).hexdigest(), status=status,
            members=[fields[key] for key in component], member_count=len(component),
            missing_execution_uids=missing, duplicate_execution_uids=duplicate_executions,
            maximum_pair_separation_arcsec=diameter, outside_tolerance_pairs=outside,
            ambiguity_reasons=reasons))
    return dict(schema_version='archive_mosaic_pointing_groups_1',
        project_code=comparison['project_code'], member_ous_uid=comparison['member_ous_uid'],
        source_name=comparison['source_name'], tolerance_arcsec=tolerance_arcsec, frame='ICRS',
        grouping_method='CROSS_EXECUTION_TOLERANCE_COMPONENTS_WITH_ALL_PAIRS_VALIDATION',
        execution_uids=expected, field_record_count=len(fields), groups=groups,
        status_counts=dict(sorted(Counter(g['status'] for g in groups).items())),
        coordinate_scope=comparison['coordinate_scope'],
        completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED', policy_status='NOT_EVALUATED',
        deduplication_status='NOT_PERFORMED', representative_coordinate_status='NOT_COMPUTED')
