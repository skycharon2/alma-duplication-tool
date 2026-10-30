"""Step 04C: explicitly opted-in V2 Archive Single/Mosaic report acceptance."""

from copy import deepcopy
import json

import pytest

from alma_duplicate.assessment import AssessmentSources, AssessmentStatus, assess_observation
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.submitted_line_assessment import (
    assess_submitted_line_mosaic_v2, assess_submitted_line_single_v2,
)
from tests.integration.test_line_preparation import EXAMPLE
from tests.integration.test_mosaic_scientific_acceptance import _line_case
from tests.integration.test_separated_setup_contract_step03ba import new_wire


def _wire(frequency="225.1", *, inventory=False, geometry="SINGLE_POINTING"):
    document = new_wire()
    raw = document["request"]
    raw["geometry"] = geometry
    raw["line_requirements"][0]["window_center"]["value"] = frequency
    raw["physical_spw_inventory_complete"] = inventory
    if geometry == "MOSAIC":
        raw["target_name"] = "proposed"
        raw["position"] = None
    return document


def _single(document):
    return assess_submitted_line_single_v2(
        document["request"], document["search_options"],
        archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json"),
    )


@pytest.mark.parametrize("frequency,expected", [
    ("225.1", Truth.TRUE), ("240", Truth.FALSE),
])
@pytest.mark.parametrize("inventory", [False, True])
def test_single_search_report_preserves_scope_source_and_provenance(frequency, expected, inventory):
    document = _wire(frequency, inventory=inventory)
    result = _single(document)
    assert result["report_version"] == "7"
    assert result["assessment_schema_version"] == "submitted_line_single_candidate_report_1"
    assert result["report_kind"] == "SUBMITTED_LINE_V2_CANDIDATE_EVALUATION"
    assert result["v2_science"]["line_evaluation_scope"] == "SUBMITTED_LINE_REQUIREMENTS_V2"
    assert result["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"
    assert result["v2_science"]["physical_inventory_affects_line_verdict"] is False
    assert result["assessment"] == "NOT_AGGREGATED"
    assert result["assessment_status"] == "COMPLETED"
    assert result["sources"]["ARCHIVE"]["status"] == "COMPLETED"
    assert result["sources"]["QUEUE"]["status"] == "NOT_SELECTED"
    assert result["request"]["raw"] == document["request"]
    assert result["request"]["normalized"]["submitted_requirement_ids"] == ["line-a"]
    assert "spectral_windows" not in result["request"]["raw"]
    assert result["evaluation_scope"]["total_retained"] == len(result["context_evaluations"])
    item = result["context_evaluations"][0]
    assert item["branches"][0]["truth"] == expected
    assert item["branches"][0]["method_version"] == "archive_line_context_submitted_or_2"
    assert item["line_pairing"]["builder_version"] == "archive_line_pair_builder_submitted_2"
    pair = item["line_pairs"][0]
    assert pair["method_version"] == "archive_line_pair_and_1"
    assert pair["attempt"]["proposed_window_id"] == "line-a"
    assert pair["attempt"]["reference"]["candidate_context_id"] == item["context_id"]
    assert len(pair["criteria"]) == 6
    assert all("eligible_for_formal_aggregation" in r for r in pair["criteria"])
    assert "PROPOSED_ENUMERATION_INCOMPLETE" not in item["branches"][0]["reasons"]
    json.dumps(result, allow_nan=False)


def test_single_two_requirements_and_extra_physical_spw_never_splice():
    document = _wire("240")
    request = document["request"]
    request["line_requirements"].append({
        "requirement_id": "line-b", "window_center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
        "correlator_mode": "FDM", "spectral_resolution": {"value": "20", "unit": "km/s"},
        "rms": {"value": "0.01", "unit": "mJy/beam"},
    })
    request["physical_spw_evidence"].append({
        "spw_id": "physical-c", "bandwidth": {"value": "2000", "unit": "MHz"},
        "bandwidth_kind": "USABLE",
    })
    result = _single(document)
    first = result["context_evaluations"][0]
    assert [p["attempt"]["proposed_window_id"] for p in first["line_pairs"]] == ["line-a", "line-b"]
    assert [p["truth"] for p in first["line_pairs"]] == ["FALSE", "FALSE"]
    assert first["branches"][0]["truth"] == "FALSE"
    request["line_requirements"][1]["rms"]["value"] = "0.3"
    improved = _single(document)["context_evaluations"][0]
    assert [p["truth"] for p in improved["line_pairs"]] == ["FALSE", "TRUE"]
    assert improved["branches"][0]["truth"] == "TRUE"


@pytest.mark.parametrize("frequency,expected", [("225.1", "TRUE"), ("240", "FALSE")])
@pytest.mark.parametrize("inventory", [False, True])
def test_mosaic_supplied_contexts_report_records_real_geometry(frequency, expected, inventory):
    document = _wire(frequency, inventory=inventory, geometry="MOSAIC")
    _, context, pointings, execution, array_evidence = _line_case()
    result = assess_submitted_line_mosaic_v2(
        document["request"], (context,), pointings,
        use_s_region=False, executions=(execution,), array_evidence=array_evidence,
    )
    assert result["schema_version"] == "submitted_line_mosaic_supplied_contexts_report_1"
    assert result["discovery_scope"] == "SUPPLIED_ARCHIVE_CONTEXTS_NOT_EXHAUSTIVE_SEARCH"
    assert result["assessment"] == "NOT_AGGREGATED"
    assert result["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"
    item = result["contexts"][0]
    assert item["context_id"] == context.context_id
    assert item["branches"][0]["truth"] == expected
    assert item["branches"][0]["method_version"] == "archive_line_context_submitted_or_2"
    assert item["line_pairs"][0]["attempt"]["reference"]["candidate_context_id"] == context.context_id
    assert item["line_pairs"][0]["criteria"][0]["criterion_id"] == "POS-MOSAIC"
    assert item["coverage"]["pointing_count"] >= 1
    json.dumps(result, allow_nan=False)


def test_mosaic_s_region_path_uses_recorded_region_evidence():
    from alma_duplicate.proposed_mosaic import import_proposed
    document = _wire("240", geometry="MOSAIC")
    _, context, _, _, _ = _line_case()
    raw = context.evidence.prepared.raw_row
    ra, dec = float(raw["s_ra"]), float(raw["s_dec"])
    pointings = import_proposed(
        ("RA,Dec,Coordinate Type,Coordinate Units\n--\n"
         f"{ra:.15g},{dec:.15g},Absolute,Degrees\n").encode("ascii"),
        source_name="proposed", array="12m",
        confirm_fixed_icrs=True, confirm_complete=True,
    )
    result = assess_submitted_line_mosaic_v2(
        document["request"], (context,), pointings,
    )
    assert result["pointing_source"] == "ARCHIVE_S_REGION"
    item = result["contexts"][0]
    assert item["coverage"]["raw_s_region"] == raw["s_region"]
    assert item["branches"][0]["truth"] == "FALSE"


def test_unavailable_archive_retains_failed_source_without_negative():
    class BrokenArchive:
        def search(self, spec):
            raise RuntimeError("Archive is offline")

    document = _wire("240")
    result = assess_submitted_line_single_v2(
        document["request"], document["search_options"], archive_client=BrokenArchive(),
    )
    assert result["assessment_status"] == "SOURCES_UNAVAILABLE"
    assert result["sources"]["ARCHIVE"]["status"] == "FAILED"
    assert result["context_evaluations"] == []
    assert result["assessment"] == "NOT_AGGREGATED"
    assert result["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"


@pytest.mark.parametrize("change", [
    lambda r: r.update(setup_complete=True),
    lambda r: r.update(line_evaluation_scope="SUBMITTED_LINE_REQUIREMENTS_V2"),
    lambda r: r.update(intents=["LINE", "CONTINUUM"]),
    lambda r: r["line_requirements"][0].pop("rms"),
])
def test_invalid_new_request_rejected_before_provider(change):
    document = _wire("240")
    change(document["request"])
    class Forbidden:
        def search(self, spec):
            pytest.fail("Invalid request reached Archive")
    with pytest.raises(ValueError):
        assess_submitted_line_single_v2(
            document["request"], document["search_options"], archive_client=Forbidden(),
        )


def test_mosaic_duplicate_context_rejected_and_default_api_still_blocked():
    document = _wire("240", geometry="MOSAIC")
    _, context, pointings, execution, evidence = _line_case()
    with pytest.raises(ValueError, match="unique original Archive"):
        assess_submitted_line_mosaic_v2(
            document["request"], (context, context), pointings,
            use_s_region=False, executions=(execution,), array_evidence=evidence,
        )
    sources = AssessmentSources(archive_kind="LIVE", archive_provider=lambda: pytest.fail("Archive provider called"))
    for geometry in ("SINGLE_POINTING", "MOSAIC"):
        raw = deepcopy(document["request"])
        raw["geometry"] = geometry
        result = assess_observation(raw, document["search_options"], sources=sources)
        assert result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
        assert result.document is None


def test_search_options_are_checked_before_archive_access():
    document = _wire()
    document["search_options"]["sources"] = ["ARCHIVE", "INVALID"]
    class Forbidden:
        def search(self, spec):
            pytest.fail("Unsupported source reached Archive")
    with pytest.raises(ValueError, match="valid shared search fields"):
        assess_submitted_line_single_v2(
            document["request"], document["search_options"], archive_client=Forbidden(),
        )
    document["search_options"]["sources"] = ["ARCHIVE"]
    document["search_options"]["radius"] = {"value": -1, "unit": "arcsec"}
    with pytest.raises(ValueError, match="readiness"):
        assess_submitted_line_single_v2(
            document["request"], document["search_options"], archive_client=Forbidden(),
        )


def test_v2_unconfigured_archive_is_reported_unavailable():
    document = _wire()
    result = assess_submitted_line_single_v2(document["request"], document["search_options"])
    assert result["assessment_status"] == "SOURCES_UNAVAILABLE"
    assert result["sources"]["ARCHIVE"]["status"] != "COMPLETED"
    assert result["assessment"] == "NOT_AGGREGATED"
