from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryResult,
    ArchiveQueryStatus,
    TapResponse,
)
from tests.unit.test_archive_contract import _field_metadata, _provenance


def _response(rows):
    return TapResponse(
        rows=rows,
        declared_columns=("value",),
        field_metadata=_field_metadata("value"),
        query_status_raw="OK",
    )


def test_response_copies_input_and_preserves_duplicate_rows():
    source = {"value": "  original  "}
    inputs = [source, source]
    response = _response(inputs)
    source["value"] = "changed"
    inputs.clear()
    assert len(response.rows) == 2
    assert response.rows[0] == response.rows[1] == {"value": "  original  "}
    assert response.rows[0] is not response.rows[1]
    with pytest.raises(TypeError):
        response.rows[0]["value"] = "changed"
    with pytest.raises(TypeError):
        response.rows[0] = {}
    with pytest.raises(FrozenInstanceError):
        response.rows = ()


@pytest.mark.parametrize("status", list(ArchiveQueryStatus))
def test_direct_result_snapshots_include_diagnostic_rows(status):
    source = {"value": b" original "}
    result = ArchiveQueryResult(
        status=status,
        rows=(source,),
        provenance=_provenance(expected_count=1, retrieved_count=1),
        field_metadata=_field_metadata("value"),
        error_kind=(ArchiveQueryErrorKind.SCHEMA_DRIFT
                    if status is ArchiveQueryStatus.ERROR else None),
    )
    source.clear()
    assert result.rows[0]["value"] == b" original "
    assert result.can_reconstruct == (status is ArchiveQueryStatus.COMPLETE)
    with pytest.raises(TypeError):
        result.rows[0]["value"] = None


def test_scalar_types_masks_and_column_order_are_preserved():
    values = [None, np.ma.masked, b" a ", " a ", True, 2, 1.2,
              complex(1, 2), float("nan"), np.int16(2), np.uint64(3),
              np.float32(1.5), np.bool_(False), np.bytes_(b" x "),
              np.str_(" x "), np.datetime64("2026-09-07"),
              np.timedelta64(2, "s")]
    row = {f"c{i}": value for i, value in enumerate(values)}
    names = tuple(row)
    result = TapResponse(
        rows=(row,), declared_columns=names,
        field_metadata=_field_metadata(*names), query_status_raw="OK",
    )
    assert tuple(result.rows[0]) == names
    for name, original in row.items():
        assert result.rows[0][name] is original
        assert type(result.rows[0][name]) is type(original)


@pytest.mark.parametrize("value", [
    [], {}, set(), bytearray(b"a"), np.array([1]), np.array(1),
    np.ma.array([1], mask=[True]), np.array([(1,)], dtype=[("x", "i4")])[0],
    object(),
])
def test_mutable_or_unsupported_cells_are_not_silently_retained(value):
    with pytest.raises(TypeError, match="row 0, column 'value'.*unsupported cell"):
        _response(({"value": value},))
