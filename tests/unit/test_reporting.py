"""JSON compatibility and atomic report publication."""
import json
from types import MappingProxyType

import pytest

from alma_duplicate.reporting import json_value, write_report


def test_mapping_and_nonfinite_values_remain_explicit():
    value = MappingProxyType({
        "missing": None,
        "invalid": float("nan"),
        "overflow": float("inf"),
        "values": (1, 2),
    })
    converted = json_value(value)
    assert converted["invalid"] == {"non_finite": "nan"}
    assert converted["overflow"] == {"non_finite": "inf"}
    assert converted["missing"] is None
    json.dumps(converted, allow_nan=False)


def test_unknown_values_are_not_silently_stringified():
    with pytest.raises(TypeError):
        json_value(object())


def test_existing_report_is_preserved_without_overwrite(tmp_path):
    path = tmp_path / "report.json"
    write_report(path, {"version": 1})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_report(path, {"version": 2})
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".alma-report-*.tmp"))
    write_report(path, {"version": 2}, overwrite=True)
    assert json.loads(path.read_text()) == {"version": 2}


def test_serialization_failure_preserves_previous_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("previous")
    with pytest.raises(TypeError):
        write_report(path, {"invalid": object()}, overwrite=True)
    assert path.read_text() == "previous"
