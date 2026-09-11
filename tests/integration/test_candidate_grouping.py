"""Observation-level presentation groups; rows keep their own contexts."""
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.domain.candidate_search import CandidateDisposition as D
from alma_duplicate.grouping import GROUPING_VERSION, group_candidates, visible_groups
from tests.integration.test_aq_equivalent_filters import CASE1_FILTERS
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_case1_live_rows import EXPECTED_MEMBER, case1_request, live_rows_client
from tests.integration.test_search_plan_spatial import validation


def case1_groups(predicates=CASE1_FILTERS, **kwargs):
    result = search_candidates(case1_request(predicates), archive_client=live_rows_client(), **kwargs)
    return result, group_candidates(result)


def test_case1_live_rows_form_one_visible_science_entry():
    result, groups = case1_groups(aq_equivalent_filters=True)
    assert sum(len(g.rows) for g in groups) == len(result.archive.rows) == 10
    visible = visible_groups(groups)
    assert [g.key for g in visible] == [(EXPECTED_MEMBER, "PKS1830-211")]
    (entry,) = visible
    assert entry.disposition is D.MATCHED_FILTERS
    assert entry.science is True and entry.key_complete
    assert len(entry.rows) == 4 and len(entry.matched_rows) == 1
    assert entry.grouping_version == GROUPING_VERSION
    assert result.assessment == "NOT_EVALUATED"


def test_without_spectral_filters_more_entries_remain_visible():
    _, groups = case1_groups(predicates=None)
    visible = {g.key[0] for g in visible_groups(groups)}
    assert EXPECTED_MEMBER in visible
    assert len(visible) > 1
    science = {g.key[0] for g in visible_groups(groups, science_only=True)}
    assert "uid://A002/X7d1738/X42" in visible and "uid://A002/X7d1738/X42" not in science


def test_every_row_stays_in_exactly_one_group_with_its_own_filters():
    result, groups = case1_groups(aq_equivalent_filters=True)
    ids = [r.context.context_id for g in groups for r in g.rows]
    assert sorted(ids) == sorted(r.context.context_id for r in result.archive.rows)
    (entry,) = [g for g in groups if g.key[0] == EXPECTED_MEMBER]
    # Grouping never copies the matched SPW's frequency result onto the other SPWs.
    assert sorted(r.disposition.value for r in entry.rows) == ["EXCLUDED"] * 3 + ["MATCHED_FILTERS"]


def test_queue_rows_group_by_project_target_and_band():
    # Two physical rows of the same target (e.g. two custom-mosaic pointings).
    q = queue_rows({}, {"Long Offset": "5"})
    result = search_candidates(validation(sources=("QUEUE",)), queue_result=q)
    groups = group_candidates(result)
    assert len(result.queue.rows) == 2
    (group,) = groups
    assert group.source == "QUEUE" and group.key_complete and len(group.key) == 3
    assert len(group.rows) == 2
    assert group.science is True
