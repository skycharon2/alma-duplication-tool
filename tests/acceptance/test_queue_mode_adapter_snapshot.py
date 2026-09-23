from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_mode_adapter import main, run
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.domain.queue import QueueParseStatus


@pytest.mark.snapshot
def test_full_population_mode_scope_separation_and_immutable_source(tmp_path):
    source = os.environ.get("ALMA_QUEUE_CSV_SNAPSHOT")
    if not source:
        pytest.skip("set ALMA_QUEUE_CSV_SNAPSHOT to pinned full CSV")
    before = Path(source).read_bytes()
    summary = run(source, tmp_path / "one", require_pinned_snapshot=True)
    assert summary["mode_counts"] == {"FDM": 15947, "TDM": 269, "UNKNOWN": 0}
    assert summary["path_counts"] == {
        "EXACT_REFERENCE": 16140,
        "N16_SCOPED_COMPATIBILITY": 76,
    }
    assert summary["single_point_scope_counts"].get("SUPPORTED") == 459
    assert summary["compatibility_mode_counts"] == {"FDM": 76}
    records = json.loads((tmp_path / "one/spws.json").read_text())
    assert len(records) == 16216
    assert (
        len(
            {(r["source"]["source_row_id"], r["source"]["spw_number"]) for r in records}
        )
        == 16216
    )
    assert all(
        r["mode_evidence"]["input"]["resolution_mhz"] == r["source"]["resolution_mhz"]
        for r in records
    )
    assert all(
        r["mode_evidence"]["mode"] in ("FDM", "TDM")
        for r in records
        if r["single_point_applicability"]["status"] != "SUPPORTED"
    )
    selected = [
        r
        for r in records
        if r["mode_evidence"]["match_path"] == "N16_SCOPED_COMPATIBILITY"
    ]
    assert len(selected) == 76
    assert all(r["source"]["resolution_raw_mhz"] for r in selected)
    raw_groups = {
        (
            r["mode_evidence"]["input"]["cycle"],
            r["mode_evidence"]["input"]["polarization"],
            r["source"]["resolution_raw_mhz"],
        )
        for r in selected
    }
    assert len(raw_groups) == 4
    assert summary == run(source, tmp_path / "two", require_pinned_snapshot=True)
    assert Path(source).read_bytes() == before
    assert (
        summary["artifacts_sha256"]["spws.json"]
        == hashlib.sha256((tmp_path / "one/spws.json").read_bytes()).hexdigest()
    )
    assert main(["--queue-csv", source, "--output-dir", str(tmp_path / "one")]) == 2


def test_pin_and_incomplete_ingestion_refused(tmp_path, monkeypatch):
    fixture = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"
    assert (
        main(
            [
                "--queue-csv",
                str(fixture),
                "--output-dir",
                str(tmp_path / "out"),
                "--require-pinned-snapshot",
            ]
        )
        == 2
    )
    parsed = QueueCsvClient().load(fixture)
    monkeypatch.setattr(
        QueueCsvClient,
        "load",
        lambda *args: replace(parsed, status=QueueParseStatus.ERROR),
    )
    assert (
        main(["--queue-csv", str(fixture), "--output-dir", str(tmp_path / "out")]) == 2
    )
    assert not (tmp_path / "out").exists()
