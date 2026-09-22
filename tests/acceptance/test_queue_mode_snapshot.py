"""Full physical-SPW census; requires the exact caller-owned Queue capture."""

import os
from pathlib import Path

import pytest

from alma_duplicate.queue_mode_census import run_census


@pytest.mark.snapshot
def test_full_queue_mode_census(tmp_path):
    raw_path = os.environ.get("ALMA_QUEUE_CSV_SNAPSHOT")
    if not raw_path:
        pytest.skip("set ALMA_QUEUE_CSV_SNAPSHOT to the pinned full CSV")
    result = run_census(
        Path(raw_path), tmp_path / "census", require_pinned_snapshot=True
    )
    assert result["denominator"]["raw_rows"] == 3200
    assert result["denominator"]["regular_rows"] == 3199
    assert result["denominator"]["regular_spws"] == 16216
    assert result["denominator"]["unique_raw_signatures"] == 39
    assert result["denominator"]["spectral_scan_rows_excluded"] == 1
    assert result["denominator"]["repeated_content_rows"] == 65
    for key, expected in (
        ("conditional_unique_configuration", (15707, 269, 240)),
        ("conditional_mode_consensus", (15947, 269, 0)),
        ("reference_only_mode_consensus", (15871, 269, 76)),
        ("source_bound", (0, 0, 16216)),
    ):
        assert tuple(result[key][m] for m in ("FDM", "TDM", "UNKNOWN")) == expected
    assert result["unique_configuration_unknown_reasons"] == {
        "AMBIGUOUS_CONFIGURATION": 240
    }
    assert result["export_compatibility_only_spws"] == 76
    single = next(
        g
        for g in result["by_group"]
        if g["field"] == "geometry" and g["value"] == "SINGLE_FIELD"
    )
    assert single["conditional_mode_consensus"]["total"] == 459
    assert single["reference_only_mode_consensus"]["UNKNOWN"] == 76
