"""Synthetic coverage contracts; these fixtures do not establish OT grid parity."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.cli.queue_mosaic_position import main
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_mosaic import reconstruct_queue_mosaics
from alma_duplicate.rules.queue_mosaic_position import (
    QueueMosaicCoverage, assess_queue_mosaic_position,
)


def point(pid, ra=10., dec=0.):
    return dict(id=pid, ra_deg=ra, dec_deg=dec, frame="ICRS")


@pytest.fixture
def case():
    fixture = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"
    report = reconstruct_queue_mosaics(parse_queue_csv_bytes(fixture.read_bytes()))
    candidate = next(c for c in report["candidates"] if c["geometry_kind"] == "CUSTOM")
    proposal = dict(frame_basis="USER_CONFIRMED_FIXED_ICRS",
                    completeness="USER_CONFIRMED_COMPLETE", array="12m",
                    points=[point("p1"), point("p2", 10.001), point("p3", 20.)])
    coverage = QueueMosaicCoverage(
        candidate["candidate_id"], report["snapshot_sha256"],
        tuple(r["source_row_id"] for r in candidate["source_rows"]),
        12., 100., "synthetic:test-frequency", (point("c1"),),
        "synthetic:test-geometry", True, True)
    return proposal, report, candidate["candidate_id"], coverage


def evaluate(case, *bindings):
    proposal, report, cid, coverage = case
    return assess_queue_mosaic_position(proposal, report, cid, bindings or (coverage,))


def test_union_counts_each_proposed_point_once_and_leaves_missing_array_unknown(case):
    c = case[3]
    result = evaluate(case, replace(c, points=(point("a"), point("b"))))
    seven, twelve = result["beam_variants"]
    assert seven["outcome"] == "UNKNOWN"
    assert twelve["outcome"] == "SATISFIED"
    assert twelve["covered_count_lower"] == 2
    assert twelve["points"][0]["matched_point_ids"] == ["a", "b"]
    assert result["duplication_status"] == "NOT_EVALUATED"
    assert result["tp_treatment"] == "IGNORED"
    json.dumps(result, allow_nan=False)


def test_exact_half_fails_and_arrays_are_not_pooled(case):
    case[0]["points"] = [point("a"), point("b", 20.)]
    result = evaluate(case, case[3], replace(case[3], diameter_m=7., points=(point("c", 20.),)))
    assert [v["outcome"] for v in result["beam_variants"]] == ["NOT_SATISFIED"]*2
    assert [v["covered_count_lower"] for v in result["beam_variants"]] == [1, 1]


def test_partial_coverage_supports_positive_but_not_negative(case):
    c = replace(case[3], complete=False)
    assert evaluate(case, c)["beam_variants"][1]["outcome"] == "SATISFIED"
    case[0]["points"] = [point("a", 20.)]
    variant = evaluate(case, c)["beam_variants"][1]
    assert variant["outcome"] == "UNKNOWN"
    assert variant["counts"]["UNKNOWN"] == 1
    assert evaluate(case)["beam_variants"][1]["outcome"] == "NOT_SATISFIED"


def test_unconfirmed_association_or_proposal_never_passes(case):
    assert evaluate(case, replace(case[3], association_confirmed=False))["beam_variants"][1]["outcome"] == "UNKNOWN"
    case[0]["completeness"] = "NOT_CONFIRMED"
    assert evaluate(case)["beam_variants"][1]["outcome"] == "UNKNOWN"


@pytest.mark.parametrize("ra,dec", [(359.999, 0.), (20., 89.9)])
def test_spherical_boundary_wrap_and_pole(case, ra, dec):
    radius = primary_beam_fwhm_deg(100., 12.) / 2
    center = SkyCoord(ra*u.deg, dec*u.deg)
    boundary = center.directional_offset_by(90*u.deg, radius*u.deg)
    case[0]["points"] = [point("edge", boundary.ra.deg, boundary.dec.deg)]
    v = evaluate(case, replace(case[3], points=(point("c", ra, dec),)))["beam_variants"][1]
    assert v["outcome"] == "UNKNOWN"
    assert v["counts"]["BOUNDARY"] == 1
    assert abs(v["points"][0]["relations"][0]["boundary_delta_arcsec"]) < 1e-6


@pytest.mark.parametrize("changes", [
    dict(candidate_id="foreign"), dict(snapshot_sha256="foreign"),
    dict(source_row_ids=()), dict(diameter_m=6.), dict(frequency_ghz=True),
    dict(frequency_ghz=float("nan")), dict(complete="true"),
    dict(association_confirmed=1), dict(geometry_evidence_ref=""),
    dict(points=(point("a"), point("a"))), dict(points=(point("a", 360.),)),
])
def test_invalid_binding_is_rejected(case, changes):
    with pytest.raises(ValueError):
        evaluate(case, replace(case[3], **changes))


def test_duplicate_branch_and_budget_rejected(case, monkeypatch):
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate(case, case[3], case[3])
    monkeypatch.setattr("alma_duplicate.rules.queue_mosaic_position.MAX_PAIRS", 2)
    with pytest.raises(ValueError, match="budget"):
        evaluate(case)


def test_cli_json_round_trip_and_overwrite_protection(case, tmp_path):
    proposal, report, cid, coverage = case
    args = ["--candidate-id", cid, "--output", str(tmp_path / "result.json")]
    for flag, data in [("proposed", proposal), ("reconstruction", report), ("coverage", [asdict(coverage)])]:
        path = tmp_path / f"{flag}.json"
        path.write_text(json.dumps(data))
        args += [f"--{flag}", str(path)]
    assert main(args) == 0
    original = (tmp_path / "result.json").read_bytes()
    assert main(args) == 2
    assert (tmp_path / "result.json").read_bytes() == original
    (tmp_path / "proposed.json").write_text("[]")
    assert main(args) == 2


def test_existing_ot_import_flows_into_queue_position(case):
    from alma_duplicate.proposed_mosaic import import_proposed
    fixture = Path(__file__).parents[1] / "fixtures/ot_pointings/c04_degrees.txt"
    proposal = import_proposed(fixture.read_bytes(), source_name="synthetic binding",
                              array="12m", confirm_fixed_icrs=True, confirm_complete=True)
    _, report, cid, coverage = case
    result = assess_queue_mosaic_position(proposal, report, cid, [
        replace(coverage, points=(point("c", 180., -30.),))])
    assert result["beam_variants"][1]["outcome"] == "SATISFIED"
    assert result["beam_variants"][1]["covered_count_lower"] == 3
    assert result["proposed"]["input_sha256"] == proposal["input_sha256"]
