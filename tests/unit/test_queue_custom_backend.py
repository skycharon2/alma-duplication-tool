"""Direct CSV pipeline: inferred branches, explicit geometry and unknown coverage."""
import csv
import io
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_custom_check import main
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_custom_backend import assess_queue_custom_csv

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def parsed(changes=None, standalone=None):
    prefix, table = FIXTURE.read_text().split("Project Code,Target Name,", 1)
    reader = csv.DictReader(io.StringIO("Project Code,Target Name,"+table))
    rows, columns = list(reader), list(reader.fieldnames)
    if standalone is not None:
        columns.append("standAlone_ACA")
        for row in rows:
            row["standAlone_ACA"] = standalone if row["Mosaic"] == "Custom" else ""
    for row in rows:
        if row["Mosaic"] == "Custom":
            row.update(RA="10", Dec="0", **{"Mos. Coord.": "ICRS"})
            if changes:
                changes(row)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return parse_queue_csv_bytes((prefix+out.getvalue()).encode())


def proposed(ra=10., dec=0., complete=True):
    return dict(frame_basis="USER_CONFIRMED_FIXED_ICRS",
        completeness="USER_CONFIRMED_COMPLETE" if complete else "NOT_CONFIRMED",
        points=[dict(id="p1", frame="ICRS", ra_deg=ra, dec_deg=dec)])


def variants(result):
    return result["candidates"][0]["position"]["beam_variants"]


def test_csv_only_mixed_arrays_computes_explicit_12m_and_keeps_aca_unknown():
    report = assess_queue_custom_csv(parsed(), proposed())
    seven, twelve = variants(report)
    assert seven["outcome"] == "UNKNOWN"
    assert seven["geometry_model"] == "UNRESOLVED_ACA_GENERATED_GRID"
    assert seven["coverage"] is None
    assert twelve["outcome"] == "SATISFIED"
    assert twelve["coverage"]["complete"] is False
    assert twelve["model_status"] == "PROVISIONAL"
    assert report["candidates"][0]["position"]["tp_treatment"] == "IGNORED"
    assert report["duplication_status"] == "NOT_EVALUATED"
    assert all(c["reason"] == "RECTANGLE_GRID_NOT_IMPLEMENTED" for c in report["excluded_mosaic_candidates"])
    json.dumps(report, allow_nan=False)


def test_12m_only_and_7m_only_reuse_array_inference():
    twelve = assess_queue_custom_csv(parsed(lambda r: r.update({"Use 7-m?": "False"})), proposed())
    assert [v["diameter_m"] for v in variants(twelve)] == [12.]
    seven = assess_queue_custom_csv(parsed(standalone="True"), proposed())
    assert [v["diameter_m"] for v in variants(seven)] == [7.]
    assert variants(seven)[0]["outcome"] == "SATISFIED"
    inferred = assess_queue_custom_csv(parsed(lambda r: r.update({"Req. Ang. Res.": "30"})), proposed())
    assert [v["diameter_m"] for v in variants(inferred)] == [7.]
    assert "EXPLICIT_POINTS_MAIN_12M_IF_PRESENT_ELSE_SOLE_7M" in inferred["candidates"][0]["profile_assumptions"]


def test_no_match_and_incomplete_proposal_do_not_claim_negative_or_positive():
    outside = assess_queue_custom_csv(parsed(), proposed(50))
    assert variants(outside)[1]["outcome"] == "UNKNOWN"
    assert variants(outside)[1]["counts"]["UNKNOWN"] == 1
    incomplete = assess_queue_custom_csv(parsed(), proposed(complete=False))
    assert variants(incomplete)[1]["outcome"] == "UNKNOWN"


@pytest.mark.parametrize("frame", ["galactic"])
def test_unresolved_coordinates_not_promoted(frame):
    result = assess_queue_custom_csv(parsed(lambda r: r.update({"Mos. Coord.": frame})), proposed())
    assert all(v["coverage"] is None for v in variants(result))
    assert "CUSTOM_CSV_COORDINATES_UNRESOLVED" in variants(result)[1]["reasons"]


def test_blank_frame_convention_and_zero_frequency_fallback_are_reported():
    result = assess_queue_custom_csv(parsed(lambda r: r.update({"Mos. Coord.": "", "Ref.Frequency": "0"})), proposed())
    candidate = result["candidates"][0]
    assert candidate["frequency"]["source"] == "sky_spw_weighted_mean"
    assert "BLANK_FRAME_EQUATORIAL_CONVENTION" in candidate["source_rows"][0]["center"]["reasons"]
    assert variants(result)[1]["outcome"] == "SATISFIED"


def test_setup_split_is_not_union_and_exact_selection_is_source_bound():
    count = 0
    def edit(row):
        nonlocal count
        row["Ref.Frequency"] = str(100+count)
        count += 1
    p = parsed(edit)
    result = assess_queue_custom_csv(p, proposed())
    assert len(result["candidates"]) == 2
    cid = result["candidates"][0]["candidate_id"]
    selected = assess_queue_custom_csv(p, proposed(), candidate_id=cid)
    assert len(selected["candidates"]) == 1
    assert len(selected["candidates"][0]["source_rows"]) == 1
    assert any(c["reason"] == "OUTSIDE_SELECTED_CANDIDATE" for c in selected["excluded_mosaic_candidates"])
    with pytest.raises(ValueError, match="Custom"):
        assess_queue_custom_csv(p, proposed(), candidate_id="foreign")
    with pytest.raises(ValueError, match="Custom"):
        assess_queue_custom_csv(p, proposed(), candidate_id=result["excluded_mosaic_candidates"][0]["candidate_id"])


def test_bad_array_evidence_retains_candidate():
    result = assess_queue_custom_csv(parsed(standalone="invalid"), proposed())
    assert len(result["candidates"]) == 1
    assert not variants(result)
    assert result["candidates"][0]["position"]["reasons"] == ["ARRAY_INFERENCE_UNRESOLVED"]


def test_cli_needs_only_csv_and_proposed_json_and_protects_output(tmp_path):
    root = Path(__file__).parents[2]
    request = tmp_path / "proposed.json"
    request.write_text(json.dumps(proposed(150, -30)))
    out = tmp_path / "position.json"
    args = ["--queue-csv", str(root / "examples/queue-mosaic-ot/custom-engineering.csv"),
            "--proposed", str(request), "--output", str(out)]
    assert main(args) == 0
    before = out.read_bytes()
    assert variants(json.loads(before))[1]["outcome"] == "SATISFIED"
    assert main(args) == 2 and out.read_bytes() == before
    request.write_text("[]")
    assert main(args) == 2


def test_batch_budget_and_invalid_proposal_rejected(monkeypatch):
    with pytest.raises(ValueError):
        assess_queue_custom_csv(parsed(), {})
    with pytest.raises(ValueError):
        assess_queue_custom_csv(parsed(), proposed(), boundary_epsilon_arcsec=float("nan"))
    monkeypatch.setattr("alma_duplicate.queue_custom_backend.MAX_TOTAL_PAIRS", 1)
    with pytest.raises(ValueError, match="budget"):
        assess_queue_custom_csv(parsed(), proposed())


@pytest.mark.parametrize("ra,dec,east,north,expected", [
    (359.999, 0, 7.2, 0, (.001, 0)),
    (10, 60, 0, 36, (10, 60.01)),
    (10, -60, 0, -36, (10, -60.01)),
])
def test_direct_csv_retains_signed_spherical_coordinates(ra, dec, east, north, expected):
    p = parsed(lambda r: r.update(RA=str(ra), Dec=str(dec),
        **{"Long Offset": str(east), "Lat Offset": str(north)}))
    result = assess_queue_custom_csv(p, proposed(*expected))
    coverage = variants(result)[1]["coverage"]
    assert len(coverage["points"]) == 2  # Repeated rows keep source identity.
    for point in coverage["points"]:
        assert (point["ra_deg"], point["dec_deg"]) == pytest.approx(expected, abs=1e-9)
    assert variants(result)[1]["counts"]["INSIDE"] == 1
