"""End-to-end offline execution tests; no confirmed duplicate labels."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.domain.candidate_search import CandidateDisposition as D, SearchSourceStatus as S
from alma_duplicate.domain.spatial import PositionInterpretation
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus, ArchiveQueryErrorKind
from alma_duplicate.search_plan import build_search_plan
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from tests.integration.test_search_plan_spatial import validation, archive
from tests.unit.test_queue_csv_parser import _records, _indices, _render


def queue_rows(*changes):
    original = _records()
    records = original[:41]
    columns = _indices(original)
    for change in changes:
        row = original[41].copy()
        values = {"RA": "0", "Dec": "0", "Long Offset": "0", "Lat Offset": "0"} | change
        for key, value in values.items():
            row[columns[key]] = value
        records.append(row)
    return parse_queue_csv_bytes(_render(records))


def interpretations(q):
    return tuple(PositionInterpretation(c.context_id, "ICRS", "FIXED", "synthetic-test-evidence")
                 for c in build_queue_contexts(q).contexts)


class SpyClient:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def search(self, spec):
        self.calls.append(spec)
        if self.error:
            raise self.error
        return self.result


def test_both_sources_execute_and_preserve_original_context_evidence():
    v = validation()
    a, _ = archive(build_search_plan(v))
    q = queue_rows({})
    client = SpyClient(a)
    result = search_candidates(v, archive_client=client, queue_result=q, interpretations=interpretations(q))
    assert client.calls == [result.plan.for_source("ARCHIVE").archive_query]
    assert result.archive.query_binding.status == "MATCHED"
    assert result.archive.status is S.COMPLETED and result.queue.status is S.COMPLETED
    assert [r.disposition for r in result.candidates] == [D.MATCHED_FILTERS, D.MATCHED_FILTERS]
    assert result.archive.source_record is a and result.queue.source_record is q
    assert result.archive.server_predicate_indices == (0,)
    assert result.execution == "FINISHED" and result.plan.execution == "NOT_EXECUTED"
    assert result.assessment == "NOT_EVALUATED"
    assert result.finished_at >= result.started_at


def test_real_archive_client_with_fake_tap_is_bound_and_executed():
    from alma_duplicate.clients.archive_client import ArchiveClient
    from alma_duplicate.clients.archive_contract import TapResponse
    from tests.fakes import FakeTapExecutor
    from tests.integration.test_archive_pipeline_fixture import _field_metadata
    v = validation(sources=("ARCHIVE",))
    a, _ = archive(build_search_plan(v))
    executor = FakeTapExecutor([
        TapResponse(rows=({"total_matches": 1},), declared_columns=("total_matches",),
                    field_metadata=_field_metadata(("total_matches",)), query_status_raw="OK"),
        TapResponse(rows=a.rows, declared_columns=tuple(a.rows[0]),
                    field_metadata=a.field_metadata, query_status_raw="OK"),
    ])
    real_client = ArchiveClient("https://example.invalid/tap", executor=executor)

    class CoreClient:
        def search(self, spec):
            return real_client.search(spec, optional_columns=())

    result = search_candidates(v, archive_client=CoreClient())
    assert result.archive.status is S.COMPLETED
    assert result.archive.query_binding.status == "MATCHED"
    assert len(result.candidates) == 1


def test_empty_results_finish_without_duplicate_absence_verdict():
    v = validation()
    a, _ = archive(build_search_plan(v))
    a = replace(a, rows=(), provenance=replace(a.provenance, expected_count=0, retrieved_count=0))
    result = search_candidates(v, archive_result=a, queue_result=queue_rows())
    assert result.archive.status is S.COMPLETED and result.queue.status is S.COMPLETED
    assert result.candidates == () and result.total_retained == 0
    assert result.assessment == "NOT_EVALUATED" and not result.truncated


@pytest.mark.parametrize("status", [ArchiveQueryStatus.OVERFLOW, ArchiveQueryStatus.COUNT_MISMATCH])
def test_incomplete_query_retains_raw_result_and_queue_succeeds(status):
    v = validation()
    a, _ = archive(build_search_plan(v))
    a = replace(a, status=status)
    q = queue_rows({})
    result = search_candidates(v, archive_result=a, queue_result=q)
    assert result.archive.status is S.INCOMPLETE
    assert result.archive.source_record is a and not result.archive.rows
    assert result.archive.query_binding.status == "MATCHED"
    assert result.queue.status is S.COMPLETED and len(result.candidates) == 1
    assert not result.archive.requested_filters_fully_evaluated


def test_binding_mismatch_prevents_context_filtering():
    v = validation()
    a, _ = archive(build_search_plan(validation(ra=10)))
    q = queue_rows({})
    result = search_candidates(v, archive_result=a, queue_result=q)
    assert result.archive.status is S.FAILED
    assert result.archive.query_binding.status == "MISMATCH"
    assert result.archive.rows == ()
    assert len(result.queue.retained_rows) == 1


def test_archive_exception_does_not_abort_queue():
    q = queue_rows({})
    client = SpyClient(error=RuntimeError("fixture service failure"))
    result = search_candidates(validation(), archive_client=client, queue_result=q)
    assert result.archive.status is S.FAILED
    assert "ACQUIRE_FAILED" in result.archive.reasons
    assert result.queue.status is S.COMPLETED


def test_archive_error_result_preserves_service_diagnostics():
    v = validation()
    a, _ = archive(build_search_plan(v))
    a = replace(a, status=ArchiveQueryStatus.ERROR,
                error_kind=ArchiveQueryErrorKind.SERVICE_ERROR, error_message="fixture failure")
    result = search_candidates(v, archive_result=a)
    assert result.archive.status is S.FAILED and result.archive.source_record is a
    assert result.archive.source_record.error_message == "fixture failure"


def test_queue_strict_failure_preserves_raw_rows_and_archive():
    v = validation()
    a, _ = archive(build_search_plan(v))
    q = queue_rows({"Req.Sensitivity": ""})
    assert not q.can_reconstruct
    result = search_candidates(v, archive_result=a, queue_result=q)
    assert result.queue.status is S.FAILED and result.queue.source_record is q
    assert q.raw_rows and q.issues and not result.queue.rows
    assert result.archive.status is S.COMPLETED


@pytest.mark.parametrize("change", [{}, {"Long Offset": "1"}, {"Mosaic": "Custom"}])
def test_unevaluated_queue_geometry_is_retained(change):
    q = queue_rows(change)
    result = search_candidates(validation(sources=("QUEUE",)), queue_result=q)
    assert len(result.candidates) == 1
    row = result.candidates[0]
    assert row.disposition is D.RETAINED_UNEVALUATED
    assert row.filters[0].outcome == "NOT_EVALUATED"
    assert not result.queue.requested_filters_fully_evaluated


def test_known_outside_queue_row_is_auditable_but_not_retained():
    q = queue_rows({"RA": "5"})
    result = search_candidates(validation(sources=("QUEUE",)), queue_result=q,
                               interpretations=interpretations(q))
    assert not result.candidates
    assert result.queue.rows[0].disposition is D.EXCLUDED
    assert result.queue.rows[0].filters[0].spatial.separation_deg == pytest.approx(5)


def test_archive_server_local_disagreement_is_not_silent_exclusion():
    v = validation(sources=("ARCHIVE",))
    a, _ = archive(build_search_plan(v), region="CIRCLE ICRS 5 0 0.01")
    result = search_candidates(v, archive_result=a)
    assert len(result.candidates) == 1
    row = result.candidates[0]
    assert row.disposition is D.RETAINED_UNEVALUATED
    assert row.filters[0].spatial.status == "OUTSIDE"
    assert "SERVER_LOCAL_SPATIAL_DISAGREEMENT" in row.filters[0].reasons


def test_skipped_filters_remain_visible_even_for_empty_source():
    v = validation(sources=("QUEUE",), predicates=[
        {"field": "frequency", "operator": "=", "quantity": {"value": 100, "unit": "GHz"}},
    ])
    q = queue_rows({})
    result = search_candidates(v, queue_result=q, interpretations=interpretations(q))
    assert result.candidates[0].filters[1].outcome == "SKIPPED"
    assert result.candidates[0].disposition is D.RETAINED_UNEVALUATED
    assert not result.queue.requested_filters_fully_evaluated
    empty = search_candidates(v, queue_result=queue_rows())
    assert not empty.queue.requested_filters_fully_evaluated


def test_angular_filter_is_executed_after_spatial_and_missing_does_not_exclude():
    v = validation(sources=("ARCHIVE",), predicates=[
        {"field": "angular_resolution", "operator": "<", "quantity": {"value": .5, "unit": "arcsec"}},
    ])
    a, _ = archive(build_search_plan(v))
    result = search_candidates(v, archive_result=a)
    assert result.archive.rows[0].filters[1].outcome == "NO_MATCH"
    assert not result.candidates
    a, _ = archive(build_search_plan(v), spatial_resolution=None)
    missing = search_candidates(v, archive_result=a)
    assert missing.candidates[0].disposition is D.RETAINED_UNEVALUATED


def test_global_limit_is_after_processing_and_has_per_source_omissions():
    v = validation()
    v = replace(v, search_options=replace(v.search_options, result_limit=1))
    a, _ = archive(build_search_plan(v))
    q = queue_rows({}, {"RA": ".1"})
    result = search_candidates(v, archive_result=a, queue_result=q, interpretations=interpretations(q))
    assert result.total_retained == 3 and len(result.candidates) == 1 and result.truncated
    assert len(result.queue.rows) == 2
    assert len(result.queue.omitted_candidate_ids) == 2
    assert result.archive.omitted_candidate_ids == ()


def test_requested_source_order_controls_display_limit_only():
    v = validation(sources=("QUEUE", "ARCHIVE"))
    v = replace(v, search_options=replace(v.search_options, result_limit=1))
    a, _ = archive(build_search_plan(v))
    result = search_candidates(v, archive_result=a, queue_result=queue_rows({}))
    assert result.candidates[0].context.reference.source == "QUEUE"
    assert len(result.archive.omitted_candidate_ids) == 1
    assert result.archive.status is S.COMPLETED


def test_unselected_source_never_calls_client():
    client = SpyClient(error=AssertionError("should not run"))
    result = search_candidates(validation(sources=("QUEUE",)), archive_client=client, queue_result=queue_rows())
    assert not client.calls and result.archive.status is S.NOT_SELECTED


def test_missing_selected_input_is_distinct_from_empty_success():
    result = search_candidates(validation())
    assert result.archive.status is S.NOT_PROVIDED and result.queue.status is S.NOT_PROVIDED
    assert not result.archive.requested_filters_fully_evaluated


def test_invalid_request_fails_before_any_client_call():
    from alma_duplicate.request_validation import validate_proposed_observation
    client = SpyClient()
    with pytest.raises(ValueError):
        search_candidates(validate_proposed_observation({}, {}), archive_client=client)
    assert not client.calls


def test_conflicting_archive_input_and_duplicate_interpretation_are_rejected():
    v = validation()
    a, _ = archive(build_search_plan(v))
    with pytest.raises(ValueError):
        search_candidates(v, archive_client=SpyClient(a), archive_result=a)
    q = queue_rows({})
    interpretation = interpretations(q)[0]
    with pytest.raises(ValueError):
        search_candidates(v, queue_result=q, interpretations=(interpretation, interpretation))


def test_unused_interpretation_is_reported_not_silently_discarded():
    item = PositionInterpretation("not-in-this-run", "ICRS", "FIXED", "fixture")
    result = search_candidates(validation(sources=("QUEUE",)), queue_result=queue_rows(), interpretations=(item,))
    assert result.unused_interpretation_ids == ("not-in-this-run",)


def test_row_adapter_exception_is_retained_and_does_not_stop_other_rows(monkeypatch):
    import alma_duplicate.candidate_search as service
    original = service.adapt_spatial
    q = queue_rows({}, {"RA": ".1"})
    bad_id = build_queue_contexts(q).contexts[0].context_id

    def fail_one(context, *args, **kwargs):
        if context.context_id == bad_id:
            raise ValueError("fixture bad spatial evidence")
        return original(context, *args, **kwargs)

    monkeypatch.setattr(service, "adapt_spatial", fail_one)
    result = search_candidates(validation(sources=("QUEUE",)), queue_result=q, interpretations=interpretations(q))
    assert len(result.candidates) == 2
    assert {r.disposition for r in result.candidates} == {D.MATCHED_FILTERS, D.RETAINED_UNEVALUATED}


def test_queue_file_read_error_does_not_abort_archive(tmp_path):
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    v = validation()
    a, _ = archive(build_search_plan(v))
    result = search_candidates(v, archive_result=a,
                               queue_loader=lambda: QueueCsvClient().load(tmp_path / "absent.csv"))
    assert result.queue.status is S.FAILED
    assert result.queue.input_mode == "LOADER"
    assert "QueueCsvReadError" in result.queue.reasons
    assert result.archive.status is S.COMPLETED


def test_queue_loader_is_not_called_for_unselected_source():
    def loader():
        raise AssertionError("must not load")
    result = search_candidates(validation(sources=("ARCHIVE",)), queue_loader=loader)
    assert result.queue.status is S.NOT_SELECTED


def test_queue_loader_and_result_cannot_be_combined():
    with pytest.raises(ValueError):
        search_candidates(validation(), queue_result=queue_rows(), queue_loader=lambda: queue_rows())


def test_real_queue_client_loader_preserves_source_dates(tmp_path):
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    path = tmp_path / "queue.csv"
    path.write_bytes(_render(_records()))
    result = search_candidates(validation(sources=("QUEUE",)),
                               queue_loader=lambda: QueueCsvClient().load(path))
    assert result.queue.status is S.COMPLETED
    assert len(result.queue.rows) == 13
    assert result.queue.source_record.snapshot.retrieved_at is None
    assert str(result.queue.source_record.snapshot.source_as_of) == "2026-03-03"


@pytest.mark.parametrize("source", ["ARCHIVE", "QUEUE"])
def test_provider_returning_none_is_failure_not_missing_input(source):
    kwargs = {"archive_client": SpyClient()} if source == "ARCHIVE" else {"queue_loader": lambda: None}
    result = search_candidates(validation(sources=(source,)), **kwargs)
    execution = result.archive if source == "ARCHIVE" else result.queue
    assert execution.status is S.FAILED


def test_explicit_science_server_condition_has_execution_record():
    v = validation(sources=("ARCHIVE",))
    plan = build_search_plan(v, archive_science_only=True)
    a, _ = archive(plan)
    result = search_candidates(v, archive_result=a, archive_science_only=True)
    assert result.archive.server_predicate_indices == (0, 1)
    assert result.archive.rows[0].filters[1].outcome == "MATCH"
    row = dict(a.rows[0]) | {"science_observation": "F"}
    bad = search_candidates(v, archive_result=replace(a, rows=(row,)), archive_science_only=True)
    assert bad.candidates[0].filters[1].outcome == "NOT_EVALUATED"


def test_definite_filter_exclusion_still_retains_unevaluated_geometry_record():
    v = validation(sources=("QUEUE",), predicates=[
        {"field": "angular_resolution", "operator": "<",
         "quantity": {"value": .5, "unit": "arcsec"}},
    ])
    q = queue_rows({"Req. Ang. Res.": "2"})
    result = search_candidates(v, queue_result=q)
    assert not result.candidates
    row = result.queue.rows[0]
    assert row.disposition is D.EXCLUDED
    assert row.filters[0].outcome == "NOT_EVALUATED"
    assert row.filters[1].outcome == "NO_MATCH"
    assert result.queue.plan.predicates[1].source_field == "Req. Ang. Res."
    assert result.queue.unevaluated_rows == (row,)
