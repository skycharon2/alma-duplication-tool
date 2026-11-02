"""Offline production-client coverage discovery; no new position verdicts."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_client import ArchiveClient
from alma_duplicate.clients.archive_contract import TapResponse
from alma_duplicate.clients.archive_queries import (
    ArchiveQuerySpec, build_count_adql, build_retrieval_adql,
)
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.search_plan import build_search_plan
from tests.fakes import FakeTapExecutor
from tests.integration.test_archive_pipeline_fixture import _field_metadata
from tests.integration.test_auto_retrieval import auto_payload, validate
from tests.integration.test_search_plan_spatial import archive, queue


def test_union_predicate_is_shared_by_count_and_retrieval():
    spec = ArchiveQuerySpec(0, 0, 0.1, spatial_strategy='CENTER_OR_MOSAIC_REGION')
    count, retrieval = build_count_adql(spec), build_retrieval_adql(spec)
    assert count.split('WHERE', 1)[1] == retrieval.split('WHERE', 1)[1]
    assert " OR (is_mosaic = 'T' AND 1 = INTERSECTS(s_region," in count
    assert "science_observation = 'T'" in count
    assert "CONTAINS(POINT('ICRS', s_ra, s_dec)" in count


@pytest.mark.parametrize('center_ra', [5., 0.])
def test_far_or_near_mosaic_survives_with_member_identity_and_queue(center_ra):
    data = auto_payload(('ARCHIVE', 'QUEUE'), limit=100)
    data['request']['position'].update(ra=0, dec=0)
    validation = validate(data)
    plan = build_search_plan(validation)
    source, _ = archive(plan, mosaic='T', s_ra=center_ra,
                        region='Polygon ICRS 359 -1 1 -1 1 1 359 1')
    # Two independent Members of the same project must not be collapsed.
    rows = (source.rows[0], dict(source.rows[0]) | {
        'member_ous_uid': 'uid://A001/Xtest/X2',
        'obs_publisher_did': 'uid://A001/Xtest/X2',
    })
    executor = FakeTapExecutor([
        TapResponse(rows=({'total_matches': 2},), declared_columns=('total_matches',),
                    field_metadata=_field_metadata(('total_matches',)), query_status_raw='OK'),
        TapResponse(rows=rows, declared_columns=tuple(rows[0]),
                    field_metadata=source.field_metadata, query_status_raw='OK'),
    ])
    client = ArchiveClient('https://example.invalid/tap', executor=executor)

    class CoreClient:
        def search(self, spec):
            assert spec.spatial_strategy == 'CENTER_OR_MOSAIC_REGION'
            return client.search(spec, optional_columns=())

    queue_source, _ = queue()
    result = search_candidates(validation, archive_client=CoreClient(), queue_result=queue_source)
    assert result.archive.status == 'COMPLETED'
    assert result.archive.query_binding.status == 'MATCHED'
    assert result.queue.status == 'COMPLETED'
    contexts = result.archive.retained_rows
    assert contexts
    assert len({r.context.evidence.prepared.raw_row['member_ous_uid'] for r in contexts}) == 2
    assert len({r.context.context_id for r in contexts}) == len(contexts)
    for row in contexts:
        assert 'BOUND_QUERY_REPORTED_CENTER_OR_MOSAIC_REGION_IN_SCOPE' in row.filters[0].reasons
        assert evaluate_position_single(validation.request, row.context, row.spatial_evidence).outcome == "SATISFIED"


def test_failed_combined_query_does_not_retry_center_only_or_stop_queue():
    calls = []

    class BrokenClient:
        def search(self, spec):
            calls.append(spec)
            raise RuntimeError('coverage query failed')

    queue_source, _ = queue()
    result = search_candidates(validate(auto_payload(('ARCHIVE', 'QUEUE'))),
                               archive_client=BrokenClient(), queue_result=queue_source)
    assert len(calls) == 1
    assert result.archive.status == 'FAILED'
    assert result.queue.status == 'COMPLETED'
    assert not result.archive.retained_rows


def test_center_only_supplied_result_cannot_claim_expanded_coverage():
    validation = validate(auto_payload())
    plan = build_search_plan(validation)
    old_query = replace(plan.for_source('ARCHIVE').archive_query, spatial_strategy='CENTER')
    old_plan = replace(plan, sources=(replace(plan.for_source('ARCHIVE'), archive_query=old_query),))
    source, _ = archive(old_plan)
    result = search_candidates(validation, archive_result=source)
    assert result.archive.status == 'FAILED'
    assert 'QUERY_BINDING_FAILED' in result.archive.reasons
