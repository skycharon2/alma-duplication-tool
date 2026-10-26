"""Default main entry evaluates bound regions without package/AQ acquisition."""

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from alma_duplicate.assessment import (
    assess_observation,
    AssessmentSources,
    ArchiveInput,
)
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.proposed_mosaic import import_proposed
from tests.integration.test_case2_mosaic_acceptance import ROOT, captured_metadata


def run_case(tmp_path, monkeypatch, mode="continuum", variant="positive"):
    import alma_duplicate.mosaic_backend as backend

    payload = json.loads(
        Path(f"examples/mosaic/case2/{mode}-test-request.json").read_text()
    )
    request = payload["request"]
    if variant == "angular":
        request["angular_resolution"]["value"] = 1.0
    if variant == "frequency":
        if mode == "continuum":
            request["representative_frequency"]["value"] = 100
        else:
            request["spectral_windows"][0]["center"]["value"] = 100
    proposed = import_proposed(
        (ROOT / "ot-12m.txt").read_bytes(),
        source_name=request["target_name"],
        array="12m",
        confirm_fixed_icrs=True,
        confirm_complete=True,
    )
    if variant == "half":
        points = proposed["points"]
        proposed["points"] = points[:2] + [
            dict(points[0], id="out1", ra_deg=180),
            dict(points[0], id="out2", ra_deg=181),
        ]

    def forbidden(*a, **k):
        raise AssertionError("No package, readiness or AQ acquisition allowed")

    monkeypatch.setattr(backend, "prepare_candidates", forbidden)
    import alma_duplicate.mosaic_readiness_binding as binding

    monkeypatch.setattr(binding, "load_candidate_catalog", forbidden)
    monkeypatch.setattr(binding, "verify_candidate_readiness", forbidden)
    monkeypatch.setattr(
        backend,
        "discover_candidates",
        lambda *a, **k: dict(
            status="COMPLETED",
            plan=dict(recall_status="NOT_ESTABLISHED"),
            candidates=[
                dict(member_ous_uid="uid://A001/X133d/" + m, source_name="NGC253")
                for m in ("X9c3", "X9c5")
            ],
        ),
    )

    def search(spec):
        member = spec.member_ous_uid.split("/")[-1]
        metadata = captured_metadata(member)
        rows = [dict(r) for r in metadata.rows]
        if member == "X9c3":
            for row in rows:
                if variant == "missing":
                    row["s_region"] = None
                elif variant == "unsupported":
                    row["s_region"] = "Union ICRS (Circle 0 0 1)"
                elif variant == "single":
                    row["is_mosaic"] = "F"
                elif variant == "identity":
                    row["target_name"] = "other target"
                elif variant == "split_regions":
                    row["s_region"] = "Circle ICRS 180 0 0.001"
        return replace(metadata, rows=tuple(rows))

    result = assess_observation(
        request,
        payload["search_options"],
        sources=AssessmentSources(
            "LIVE", lambda: ArchiveInput(SimpleNamespace(search=search))
        ),
        mosaic=MosaicAssessmentInput(
            proposed, tmp_path / "run", tmp_path / "unused-cache", 1.0
        ),
    )
    assert result.validation.is_valid
    assert not (tmp_path / "unused-cache").exists()
    return json.loads((tmp_path / "run/assessment.json").read_text())


@pytest.mark.parametrize("mode", ["continuum", "line"])
@pytest.mark.parametrize(
    "variant",
    [
        "positive",
        "half",
        "angular",
        "frequency",
        "missing",
        "unsupported",
        "single",
        "identity",
        "split_regions",
    ],
)
def test_default_region_main_entry(tmp_path, monkeypatch, mode, variant):
    r = run_case(tmp_path, monkeypatch, mode, variant)
    assert r["coverage_source"] == "ARCHIVE_S_REGION"
    assert r["preparation"]["status"] == "NOT_REQUIRED"
    first, second = r["candidates"]
    assert second["status"] == "EVALUATED"
    if variant == "identity":
        assert first["status"] == "INCOMPLETE"
        return
    contexts = first["evaluation"]["contexts"]
    assert contexts
    for c in contexts:
        pos = next(x for x in c["criteria"] if x["criterion_id"] == "POS-MOSAIC")
        assert pos["method_version"] == "archive_pos_mosaic_s_region_1"
        expected = (
            None
            if variant in ("missing", "unsupported")
            else "NOT_SATISFIED"
            if variant in ("half", "split_regions")
            else "SATISFIED"
        )
        assert pos["outcome"] == expected
        assert c["coverage"]["coverage_source"] == "ARCHIVE_S_REGION"
    truths = [b["truth"] for c in contexts for b in c["branches"]]
    assert ("TRUE" in truths) == (variant in ("positive", "single"))
