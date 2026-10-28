"""Default s_region and bounded discovery acceptance for submitted LINE V2.

Geometry variants are synthetic; spectral evidence comes from Guide B replay.
These tests do not claim online Archive or exhaustive discovery acceptance.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.proposed_mosaic import import_proposed
from alma_duplicate.submitted_line_assessment import (
    assess_submitted_line_mosaic_v2, assess_submitted_line_single_v2,
)
from tests.integration.test_line_preparation import EXAMPLE
from tests.integration.test_mosaic_scientific_acceptance import _line_case
from tests.integration.test_submitted_line_assessment_step04c import _wire, _single


def mosaic_case(region="Circle ICRS 0 0 0.1", positions=(0, 0.01, 1)):
    _, context, _, _, _ = _line_case()
    prepared = context.evidence.prepared
    context = replace(context, evidence=replace(
        context.evidence, prepared=replace(
            prepared, raw_row=dict(prepared.raw_row, s_region=region),
        ),
    ))
    content = "RA,Dec,Coordinate Type,Coordinate Units\n--\n" + "".join(
        f"{ra},0,Absolute,Degrees\n" for ra in positions
    )
    proposed = import_proposed(
        content.encode(), source_name="proposed", array="12m",
        confirm_fixed_icrs=True, confirm_complete=True,
    )
    return context, proposed


@pytest.mark.parametrize("positions,region,frequency,truth,inside", [
    ((0, 0.01, 1), "Circle ICRS 0 0 0.1", "225.1", "TRUE", 2),
    ((0, 1), "Circle ICRS 0 0 0.1", "225.1", "FALSE", 1),
    ((0, 0.01, 1), "Circle ICRS 0 0 0.1", "240", "FALSE", 2),
    ((0, 0.01, 1), None, "225.1", "UNKNOWN", 0),
])
@pytest.mark.parametrize("inventory", [False, True])
def test_default_region_scope(positions, region, frequency, truth, inside, inventory):
    context, proposed = mosaic_case(region, positions)
    wire = _wire(frequency, inventory=inventory, geometry="MOSAIC")
    result = assess_submitted_line_mosaic_v2(wire["request"], [context], proposed)
    item = result["contexts"][0]
    assert result["pointing_source"] == "ARCHIVE_S_REGION"
    assert item["coverage"]["raw_s_region"] == region
    assert item["coverage"]["inside_count"] == inside
    assert item["coverage"]["pointing_count"] == len(positions)
    assert item["branches"][0]["truth"] == truth
    pair = item["line_pairs"][0]
    assert pair["truth"] == truth
    position = next(c for c in pair["criteria"] if c["criterion_id"] == "POS-MOSAIC")
    assert position["method_version"] == "archive_pos_mosaic_s_region_1"
    assert pair["attempt"]["reference"]["candidate_context_id"] == context.context_id
    assert result["assessment"] == "NOT_AGGREGATED"
    assert result["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"


@pytest.mark.parametrize("rms,truth", [("0.01", "FALSE"), ("0.3", "TRUE")])
def test_mosaic_requirements_cannot_splice_frequency_and_sensitivity(rms, truth):
    context, proposed = mosaic_case()
    wire = _wire("240", geometry="MOSAIC")
    second = deepcopy(wire["request"]["line_requirements"][0])
    second.update(requirement_id="line-b")
    second["window_center"]["value"] = "225.1"
    second["rms"]["value"] = rms
    wire["request"]["line_requirements"].append(second)
    item = assess_submitted_line_mosaic_v2(wire["request"], [context], proposed)["contexts"][0]
    assert [p["truth"] for p in item["line_pairs"]] == ["FALSE", truth]
    assert item["branches"][0]["truth"] == truth
    assert [p["attempt"]["proposed_window_id"] for p in item["line_pairs"]] == ["line-a", "line-b"]


def test_display_limit_does_not_discard_scientific_contexts():
    wire = _wire()
    full = _single(wire)
    wire["search_options"]["result_limit"] = 1
    limited = _single(wire)
    assert len(full["context_evaluations"]) > 1
    assert limited["context_evaluations"] == full["context_evaluations"]


@pytest.mark.parametrize("mode,source,status", [
    ("empty", "COMPLETED", "COMPLETED"),
    ("overflow", "INCOMPLETE", "SOURCES_UNAVAILABLE"),
    ("failure", "FAILED", "SOURCES_UNAVAILABLE"),
])
def test_empty_incomplete_and_failed_sources_are_distinct(mode, source, status):
    class Provider:
        def search(self, spec):
            if mode == "failure":
                raise RuntimeError("Controlled provider failure")
            recorded = RecordedArchiveClient(EXAMPLE / "archive/manifest.json").search(spec)
            if mode == "overflow":
                return replace(recorded, status=ArchiveQueryStatus.OVERFLOW)
            return replace(recorded, rows=(), provenance=replace(
                recorded.provenance, expected_count=0, retrieved_count=0,
            ))

    wire = _wire()
    result = assess_submitted_line_single_v2(
        wire["request"], wire["search_options"], archive_client=Provider(),
    )
    assert result["sources"]["ARCHIVE"]["status"] == source
    assert result["assessment_status"] == status
    assert result["context_evaluations"] == []
    assert result["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"
