"""Local readiness receipts must bind to package bytes and AQ source identity."""

import json
from pathlib import Path

import pytest

from alma_duplicate.archive_array_evidence import load_archive_array_catalog
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.mosaic_readiness_binding import verify_candidate_readiness
from tests.unit.test_archive_mosaic_pointings import package as package


def _candidate(package, path, report):
    return dict(
        package_audit_dir=str(package), readiness_file=str(path),
        member_ous_uid=report["member_ous_uid"],
        source_name=report["source_name"],
    )


def test_verifies_real_package_and_rejects_tampered_readiness(tmp_path, package):
    catalog = load_archive_array_catalog(
        Path("tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json")
    )
    report = build_readiness(package, catalog=catalog)
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(report))
    candidate = _candidate(package, path, report)
    verified = verify_candidate_readiness(candidate, catalog=catalog)
    expected = {
        e["asdm_uid"] for e in report["executions"]
        if e["fields"] and all(f["position_status"] == "EVIDENCE_BOUND" for f in e["fields"])
    }
    assert verified == expected
    report["executions"][0]["fields"][0]["position_status"] = "EVIDENCE_BOUND" if (
        report["executions"][0]["fields"][0]["position_status"] != "EVIDENCE_BOUND"
    ) else "UNAVAILABLE"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="differs from verified"):
        verify_candidate_readiness(candidate, catalog=catalog)


def test_rejects_wrong_candidate_identity(tmp_path, package):
    catalog = load_archive_array_catalog(
        Path("tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json")
    )
    report = build_readiness(package, catalog=catalog)
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(report))
    candidate = _candidate(package, path, report)
    candidate["source_name"] = "another-source"
    with pytest.raises(ValueError, match="another candidate"):
        verify_candidate_readiness(candidate, catalog=catalog)
