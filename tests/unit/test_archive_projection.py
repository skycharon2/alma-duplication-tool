from dataclasses import replace

import pytest

from alma_duplicate.clients import (
    ARCHIVE_CORE_COLUMNS, ARCHIVE_OPTIONAL_COLUMNS, ARCHIVE_SELECTED_COLUMNS,
    REQUIRED_ARCHIVE_COLUMNS, ArchiveClient, ArchiveOptionalColumnStatus as Status,
    ArchiveQueryErrorKind, ArchiveQueryStatus, TapExecutionError, TapResponse,
)
from tests.fakes import FakeTapExecutor
from tests.unit.test_archive_client import (
    _count_response, _field_metadata, _retrieval_response, _spec,
)


def _probe(names=ARCHIVE_OPTIONAL_COLUMNS, status="OK"):
    return TapResponse(
        rows=tuple({"column_name": name} for name in names),
        declared_columns=("column_name",),
        field_metadata=_field_metadata(("column_name",)),
        query_status_raw=status,
    )


def _run(probe, columns=ARCHIVE_CORE_COLUMNS, count=0, optional=None):
    response = _retrieval_response(count, declared_columns=columns)
    # Do not fabricate NULL cells for columns that were not returned.
    response = replace(response, rows=tuple(
        {name: row[name] for name in columns} for row in response.rows
    ))
    executor = FakeTapExecutor(
        [_count_response(count), response], projection_action=probe,
    )
    client = ArchiveClient("https://example.invalid/tap", executor=executor)
    result = client.search(_spec(), **({"optional_columns": optional} if optional is not None else {}))
    return result, executor


def test_desired_projection_does_not_expand_required_contract():
    assert len(ARCHIVE_CORE_COLUMNS) == 24
    assert len(ARCHIVE_SELECTED_COLUMNS) == 30
    assert REQUIRED_ARCHIVE_COLUMNS == frozenset(ARCHIVE_CORE_COLUMNS)
    assert not REQUIRED_ARCHIVE_COLUMNS.intersection(ARCHIVE_OPTIONAL_COLUMNS)


def test_optional_columns_probed_before_adql_and_retained_on_empty_result():
    result, executor = _run(_probe(), ARCHIVE_SELECTED_COLUMNS)
    assert result.status is ArchiveQueryStatus.COMPLETE
    plan = result.provenance.projection
    assert plan.version == "1"
    assert plan.selected_columns == ARCHIVE_SELECTED_COLUMNS
    assert len(executor.projection_calls) == 1
    assert executor.projection_calls[0].maxrec == 7
    assert all(item.status is Status.SELECTED and item.returned for item in plan.optional_columns)
    assert tuple(field.name for field in result.field_metadata) == ARCHIVE_SELECTED_COLUMNS
    assert executor.calls[0].adql.split("WHERE", 1)[1] == executor.calls[1].adql.split("WHERE", 1)[1]


def test_absent_optional_names_are_not_sent_to_service():
    result, executor = _run(_probe(("s_fov",)), ARCHIVE_CORE_COLUMNS + ("s_fov",))
    assert result.is_complete
    for item in result.provenance.projection.optional_columns:
        if item.column_name == "s_fov":
            assert item.status is Status.SELECTED and item.returned
        else:
            assert item.status is Status.NOT_IN_SCHEMA
            assert item.returned is False
            assert item.column_name not in executor.calls[1].adql


@pytest.mark.parametrize("probe", [
    _probe(status="OVERFLOW"), _probe(status=None),
    _probe(("s_fov", "s_fov")), _probe((None,)), _probe(("unknown",)),
    _probe((b"\xff",)),
    TapExecutionError(ArchiveQueryErrorKind.SERVICE_ERROR, "unavailable"),
])
def test_unusable_schema_does_not_claim_field_absence(probe):
    result, executor = _run(probe)
    assert result.is_complete
    plan = result.provenance.projection
    assert plan.probe_error
    assert plan.selected_columns == ARCHIVE_CORE_COLUMNS
    assert all(item.status is Status.SCHEMA_UNAVAILABLE for item in plan.optional_columns)
    assert result.provenance.warnings
    for name in ARCHIVE_OPTIONAL_COLUMNS:
        assert name not in executor.calls[1].adql


def test_explicit_core_only_is_not_schema_absence():
    result, executor = _run(_probe(), optional=())
    assert not executor.projection_calls
    assert all(item.status is Status.NOT_REQUESTED for item in result.provenance.projection.optional_columns)
    assert result.provenance.projection.probe_adql is None


def test_selected_but_missing_response_field_is_diagnostic_only():
    result, _ = _run(_probe(), count=1)
    assert result.is_complete
    assert all(item.status is Status.SELECTED and item.returned is False
               for item in result.provenance.projection.optional_columns)
    assert "s_fov" not in result.rows[0]
    assert result.provenance.warnings


def test_returned_null_is_preserved_separately_from_missing_column():
    result, _ = _run(_probe(), ARCHIVE_SELECTED_COLUMNS, count=1)
    assert "s_fov" in result.rows[0] and result.rows[0]["s_fov"] is None
    assert all(item.returned for item in result.provenance.projection.optional_columns)


def test_required_column_missing_still_fails_on_zero_rows():
    columns = tuple(name for name in ARCHIVE_CORE_COLUMNS if name != "obs_id")
    result, _ = _run(_probe(()), columns)
    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is ArchiveQueryErrorKind.SCHEMA_DRIFT
    assert result.missing_columns == ("obs_id",)
    assert result.provenance.projection is not None


def test_failure_before_retrieval_does_not_claim_returned_fields_missing():
    executor = FakeTapExecutor([
        TapExecutionError(ArchiveQueryErrorKind.SERVICE_ERROR, "count failed"),
    ])
    result = ArchiveClient("https://example.invalid/tap", executor=executor).search(_spec())
    assert result.status is ArchiveQueryStatus.ERROR
    assert all(item.returned is None for item in result.provenance.projection.optional_columns)


@pytest.mark.parametrize("requested", [("unknown",), ("s_fov", "s_fov")])
def test_unsupported_optional_request_fails_before_network(requested):
    executor = FakeTapExecutor([])
    with pytest.raises(ValueError):
        ArchiveClient("https://example.invalid/tap", executor=executor).search(
            _spec(), optional_columns=requested,
        )
    assert not executor.calls and not executor.projection_calls


def test_empty_schema_and_unavailable_schema_have_distinct_provenance_hashes():
    absent, _ = _run(_probe(()))
    unavailable, _ = _run(_probe(status="OVERFLOW"))
    assert absent.provenance.retrieval_adql == unavailable.provenance.retrieval_adql
    assert absent.provenance.query_hash != unavailable.provenance.query_hash
