"""Engineering parity tests; generated exports are not OT scientific acceptance."""
import csv
from dataclasses import asdict, replace
from hashlib import sha256
import io
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_mosaic_binding import main
from alma_duplicate.cli.queue_mosaic_position import main as position_main
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_mosaic import reconstruct_queue_mosaics
from alma_duplicate.queue_mosaic_binding import CustomOTBinding, _match, bind_custom_ot
from alma_duplicate.rules.queue_mosaic_position import QueueMosaicCoverage, assess_queue_mosaic_position

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def source(offsets=((0, 0), (3.6, 0)), *, ra=10., dec=0., frame="ICRS", frequency=None):
    prefix, table = FIXTURE.read_text().split("Project Code,Target Name,", 1)
    reader = csv.DictReader(io.StringIO("Project Code,Target Name,"+table))
    rows = list(reader)
    for r, (east, north) in zip([r for r in rows if r["Mosaic"] == "Custom"], offsets):
        r.update(RA=str(ra), Dec=str(dec), **{"Long Offset": str(east), "Lat Offset": str(north), "Mos. Coord.": frame})
        if frequency is not None:
            r["Ref.Frequency"] = str(frequency)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = (prefix+out.getvalue()).encode()
    parsed = parse_queue_csv_bytes(raw)
    report = reconstruct_queue_mosaics(parsed)
    candidate = next(c for c in report["candidates"] if c["geometry_kind"] == "CUSTOM")
    return raw, parsed, report, candidate


def ot(points):
    return ("RA,Dec,Coordinate Type,Coordinate Units\n--\n" +
            "\n".join(f"{ra},{dec},Absolute,DEGREES" for ra, dec in points)).encode()


def binding(case, raw, **changes):
    return replace(CustomOTBinding(case[3]["candidate_id"], case[2]["snapshot_sha256"],
        sha256(raw).hexdigest(), 12., "synthetic:target-setup-array", True, True, True), **changes)


def test_reordered_absolute_export_to_position_without_manual_point_json():
    case = source()
    raw = ot([(10.001, 0), (10, 0)])  # independently specified equatorial offsets
    audit = bind_custom_ot(case[1], raw, binding(case, raw))
    assert audit["status"] == "BOUND"
    assert audit["max_matched_error_arcsec"] < 1e-7
    assert [p["ot_point_id"] for p in audit["pairs"]] == ["row-2", "row-1"]
    coverage, = audit["coverages"]
    assert coverage["frequency_ghz"] == float(next(r for r in case[1].row_inputs if r.raw_row.row_id.value == coverage["source_row_ids"][0]).spectral.sensitivity.reference_frequency_ghz.value)
    proposed = dict(frame_basis="USER_CONFIRMED_FIXED_ICRS", completeness="USER_CONFIRMED_COMPLETE",
                    points=[dict(id="p", frame="ICRS", ra_deg=10., dec_deg=0.)])
    result = assess_queue_mosaic_position(proposed, case[2], case[3]["candidate_id"], [QueueMosaicCoverage(**coverage)])
    assert [v["outcome"] for v in result["beam_variants"]] == ["UNKNOWN", "SATISFIED"]


@pytest.mark.parametrize("offsets,ra,dec,expected", [
    (((3.6, 0), (-3.6, 0)), 359.9995, 0, [(0.0005, 0), (359.9985, 0)]),
    (((0, 3.6), (0, -3.6)), 10, 60, [(10, 60.001), (10, 59.999)]),
    (((0, 3.6), (0, -3.6)), 10, 89.9, [(10, 89.901), (10, 89.899)]),
])
def test_signed_offsets_wrap_and_nonzero_declination(offsets, ra, dec, expected):
    case = source(offsets, ra=ra, dec=dec)
    raw = ot(expected)
    assert bind_custom_ot(case[1], raw, binding(case, raw))["status"] == "BOUND"


def test_duplicate_multiplicity_and_extra_missing_points():
    case = source(((0, 0), (0, 0)))
    for points, status in [([(10, 0), (10, 0)], "BOUND"), ([(10, 0)], "UNRESOLVED"),
                           ([(10, 0), (11, 0)], "UNRESOLVED"),
                           ([(10, 0), (10, 0), (10, 0)], "UNRESOLVED")]:
        raw = ot(points)
        result = bind_custom_ot(case[1], raw, binding(case, raw))
        assert result["status"] == status
        if status == "UNRESOLVED":
            assert not result["coverages"]


def test_matching_reassigns_instead_of_greedy_nearest_and_preserves_counts():
    assert _match([[0, 1], [0]]) == {0: 1, 1: 0}
    assert len(_match([[0], [0]])) == 1


@pytest.mark.parametrize("changes", [dict(confirm_fixed_icrs=False), dict(association_confirmed=False)])
def test_coordinate_agreement_does_not_confirm_ownership(changes):
    case = source()
    raw = ot([(10, 0), (10.001, 0)])
    result = bind_custom_ot(case[1], raw, binding(case, raw, **changes))
    assert result["parity_status"] == "MATCHED"
    assert result["status"] == "UNRESOLVED" and not result["coverages"]


def test_partial_list_does_not_gain_completeness():
    case = source()
    raw = ot([(10, 0), (10.001, 0)])
    result = bind_custom_ot(case[1], raw, binding(case, raw, complete=False))
    assert result["status"] == "BOUND"
    assert result["coverages"][0]["complete"] is False


@pytest.mark.parametrize("changes", [dict(snapshot_sha256="other"), dict(ot_sha256="other"),
    dict(candidate_id="other"), dict(diameter_m=6), dict(complete="true"), dict(evidence_ref="")])
def test_foreign_or_invalid_binding_rejected(changes):
    case = source()
    raw = ot([(10, 0), (10.001, 0)])
    with pytest.raises(ValueError):
        bind_custom_ot(case[1], raw, binding(case, raw, **changes))


def test_unsupported_frame_wrong_sign_and_rectangle_do_not_bind():
    case = source(frame="galactic")
    raw = ot([(10, 0), (10.001, 0)])
    assert bind_custom_ot(case[1], raw, binding(case, raw))["coverages"] == []
    case = source()
    wrong = ot([(10, 0), (9.999, 0)])
    assert bind_custom_ot(case[1], wrong, binding(case, wrong))["coverages"] == []
    rectangle = next(c for c in case[2]["candidates"] if c["geometry_kind"] == "RECTANGLE")
    with pytest.raises(ValueError, match="Custom"):
        bind_custom_ot(case[1], raw, binding(case, raw, candidate_id=rectangle["candidate_id"]))


def test_zero_frequency_reuses_existing_queue_fallback():
    case = source(frequency=0)
    raw = ot([(10, 0), (10.001, 0)])
    result = bind_custom_ot(case[1], raw, binding(case, raw))
    assert result["frequency"]["source"] == "sky_spw_weighted_mean"
    assert result["coverages"][0]["frequency_ghz"] > 0


def test_cli_roundtrip_preserves_audit_and_protects_output(tmp_path):
    case = source()
    raw = ot([(10, 0), (10.001, 0)])
    (tmp_path / "queue.csv").write_bytes(case[0])
    (tmp_path / "ot.txt").write_bytes(raw)
    (tmp_path / "binding.json").write_text(json.dumps(asdict(binding(case, raw))))
    out = tmp_path / "audit.json"
    args = ["--queue-csv", str(tmp_path / "queue.csv"), "--ot-pointings", str(tmp_path / "ot.txt"),
            "--binding", str(tmp_path / "binding.json"), "--output", str(out)]
    assert main(args) == 0
    original = out.read_bytes()
    assert main(args) == 2 and out.read_bytes() == original
    (tmp_path / "reconstruction.json").write_text(json.dumps(case[2]))
    (tmp_path / "proposed.json").write_text(json.dumps(dict(frame_basis="USER_CONFIRMED_FIXED_ICRS",
        completeness="USER_CONFIRMED_COMPLETE", points=[dict(id="p", frame="ICRS", ra_deg=10., dec_deg=0.)])))
    pos_args = ["--reconstruction", str(tmp_path / "reconstruction.json"), "--proposed", str(tmp_path / "proposed.json"),
               "--candidate-id", case[3]["candidate_id"], "--coverage", str(out), "--output", str(tmp_path / "position.json")]
    assert position_main(pos_args) == 0
    result = json.loads((tmp_path / "position.json").read_text())
    assert result["coverage_binding_evidence"] == json.loads(original)
    assert result["beam_variants"][1]["outcome"] == "SATISFIED"


def test_budget_and_tolerance_rejected(monkeypatch):
    case = source()
    raw = ot([(10, 0), (10.001, 0)])
    for tolerance in (0, -1, 2, True, float("nan")):
        with pytest.raises(ValueError):
            bind_custom_ot(case[1], raw, binding(case, raw), tolerance_arcsec=tolerance)
    monkeypatch.setattr("alma_duplicate.queue_mosaic_binding.MAX_PAIRS", 1)
    with pytest.raises(ValueError, match="budget"):
        bind_custom_ot(case[1], raw, binding(case, raw))


def test_east_offset_at_nonzero_declination_against_analytic_spherical_solution():
    import math
    # Independent analytic destination for due-east/due-west bearings.
    case = source(((36, 0), (-36, 0)), ra=120, dec=60)
    expected = []
    for angle in (math.radians(.01), -math.radians(.01)):
        ra = 120 + math.degrees(math.atan2(math.sin(angle), math.cos(math.radians(60))*math.cos(angle)))
        dec = math.degrees(math.asin(math.sin(math.radians(60))*math.cos(angle)))
        expected.append((ra, dec))
    raw = ot(expected)
    assert bind_custom_ot(case[1], raw, binding(case, raw))["status"] == "BOUND"


def test_controlled_example_template_is_bound_to_seven_raw_offsets():
    root = Path(__file__).parents[2] / "examples/queue-mosaic-ot"
    parsed = parse_queue_csv_bytes((root / "custom-engineering.csv").read_bytes())
    report = reconstruct_queue_mosaics(parsed)
    template = json.loads((root / "binding-template.json").read_text())
    candidate, = report["candidates"]
    assert template["snapshot_sha256"] == report["snapshot_sha256"]
    assert template["candidate_id"] == candidate["candidate_id"]
    assert len(candidate["source_rows"]) == 7
    assert template["association_confirmed"] is False
    imported = list(csv.reader((root / "offsets.txt").read_text().splitlines()[2:]))
    assert [(float(r[0]), float(r[1])) for r in imported] == [
        (r.spatial.long_offset_arcsec.value, r.spatial.lat_offset_arcsec.value) for r in parsed.row_inputs]


def test_unresolved_parity_audit_does_not_supply_any_array_coverage():
    case = source()
    raw = ot([(10, 0), (11, 0)])
    audit = bind_custom_ot(case[1], raw, binding(case, raw))
    proposed = dict(frame_basis="USER_CONFIRMED_FIXED_ICRS", completeness="USER_CONFIRMED_COMPLETE",
                    points=[dict(id="p", frame="ICRS", ra_deg=10., dec_deg=0.)])
    result = assess_queue_mosaic_position(proposed, case[2], case[3]["candidate_id"], audit["coverages"])
    assert [v["outcome"] for v in result["beam_variants"]] == ["UNKNOWN", "UNKNOWN"]


def test_native_ot_controlled_seven_point_export_matches_geometry_only():
    root = Path(__file__).parents[1] / "fixtures/ot_pointings/custom_offsets_2026_11_02"
    example = Path(__file__).parents[2] / "examples/queue-mosaic-ot/custom-engineering.csv"
    parsed = parse_queue_csv_bytes(example.read_bytes())
    evidence = CustomOTBinding(**json.loads((root / "binding-geometry-only.json").read_text()))
    result = bind_custom_ot(parsed, (root / "ot-12m-absolute.txt").read_bytes(), evidence)
    assert result["parity_status"] == "MATCHED"
    assert len(result["pairs"]) == 7
    assert result["max_matched_error_arcsec"] < 1e-7
    assert result["coverages"] == []  # Coordinate parity is not setup equivalence.
    seven_raw = (root / "ot-7m-absolute.txt").read_bytes()
    seven = bind_custom_ot(parsed, seven_raw, replace(evidence, diameter_m=7,
                           ot_sha256=sha256(seven_raw).hexdigest()))
    assert seven["ot_export"]["row_count"] == 3
    assert seven["parity_status"] == "NOT_ESTABLISHED"
    assert seven["coverages"] == []
