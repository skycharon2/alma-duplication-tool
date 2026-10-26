"""Captured live TAP evidence replays through the main entry without a network."""

import json
from pathlib import Path
import shutil
import socket

import pytest

from alma_duplicate.mosaic_region_acceptance import run_acceptance, seal

ROOT = Path("tests/fixtures/archive/s_region_acceptance_2026_10_26")


def forbid(*args, **kwargs):
    raise AssertionError("Network or auxiliary preparation invoked during replay")


@pytest.mark.parametrize("mode", ["continuum", "line"])
def test_live_capture_replays_identical_decisions(tmp_path, monkeypatch, mode):
    import alma_duplicate.mosaic_backend as backend
    import alma_duplicate.mosaic_region_acceptance as acceptance

    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(acceptance, "_fetch", forbid)
    monkeypatch.setattr(acceptance, "discover_candidates", forbid)
    monkeypatch.setattr(backend, "prepare_candidates", forbid)
    summary = run_acceptance(tmp_path / "replay", replay=ROOT / mode)
    assert summary["assessment_status"] == "COMPLETED"
    assert summary["mode"] == "OFFLINE_REPLAY"
    assert summary["metadata_http_requests"] == summary["auxiliary_http_requests"] == 0
    report = json.loads((tmp_path / "replay/evaluation/assessment.json").read_text())
    assert report["source_mode"] == "REPLAY"
    actual = [
        dict(
            member_ous_uid=c["member_ous_uid"],
            status=c["status"],
            contexts=c.get("evaluation", {}).get("contexts", []),
        )
        for c in report["candidates"]
    ]
    assert actual == json.loads((ROOT / f"{mode}-expected.json").read_text())
    if mode == "continuum":
        formerly_blocked = next(
            c for c in actual if c["member_ous_uid"] == "uid://A001/X74/X176"
        )
        assert formerly_blocked["contexts"]
        assert all(
            c["coverage"]["outcome"] == "SATISFIED"
            for c in formerly_blocked["contexts"]
        )


@pytest.mark.parametrize("change", ["request", "response", "extra"])
def test_capture_tampering_is_rejected(tmp_path, change):
    capture = tmp_path / "capture"
    shutil.copytree(ROOT / "continuum", capture)
    if change == "request":
        path = capture / "request.json"
    elif change == "response":
        path = next((capture / "metadata").rglob("response-*.xml"))
    else:
        path = capture / "extra.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="checksum|unindexed"):
        run_acceptance(tmp_path / "output", replay=capture)
    assert not (tmp_path / "output").exists()


def test_incomplete_discovery_stays_incomplete(tmp_path):
    capture = tmp_path / "capture"
    shutil.copytree(ROOT / "continuum", capture)
    path = capture / "selection/discovery.json"
    report = json.loads(path.read_text())
    report["status"] = "INCOMPLETE"
    path.write_text(json.dumps(report))
    seal(capture)
    result = run_acceptance(tmp_path / "output", replay=capture)
    assert result["assessment_status"] == "INCOMPLETE"
    assert (
        result["absence_interpretation"] == "NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION"
    )


def test_changed_query_never_reuses_other_metadata(tmp_path):
    capture = tmp_path / "capture"
    shutil.copytree(ROOT / "line", capture)
    manifest = next((capture / "metadata").rglob("manifest.json"))
    data = json.loads(manifest.read_text())
    data["responses"][0]["adql"] += " "
    manifest.write_text(json.dumps(data))
    seal(capture)
    result = run_acceptance(tmp_path / "output", replay=capture)
    assert result["assessment_status"] == "INCOMPLETE"
