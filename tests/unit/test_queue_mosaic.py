"""Reconstruction tests preserve source identity and prevent false geometry claims."""

import csv
from dataclasses import replace
import io
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_mosaic import main
from alma_duplicate.domain.queue import QueueParseStatus
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_mosaic import reconstruct_queue_mosaics

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def parsed(changes=None):
    text = FIXTURE.read_text()
    prefix, table = text.split("Project Code,Target Name,", 1)
    reader = csv.DictReader(io.StringIO("Project Code,Target Name," + table))
    rows = list(reader)
    if changes:
        changes(rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    result = parse_queue_csv_bytes((prefix + out.getvalue()).encode())
    assert result.can_reconstruct
    return result


def custom(report):
    return [c for c in report["candidates"] if c["geometry_kind"] == "CUSTOM"]


def test_real_subset_preserves_associations_duplicates_and_array_inference():
    source = parsed()
    report = reconstruct_queue_mosaics(source)
    json.dumps(report, allow_nan=False)
    group, = custom(report)
    assert len(group["source_rows"]) == 2
    assert group["unique_offset_count"] == 2
    assert group["array_inference"]["classification"] == "MIX_7M_12M"
    assert group["tp_treatment"] == "IGNORED"
    assert [v["diameter_m"] for v in group["beam_variants"]] == [7, 12]
    assert all(v["pointing_centers_icrs"] is None for v in group["beam_variants"])
    assert group["coverage_completeness"] == "NOT_ESTABLISHED"
    assert report["summary"]["exact_repeated_mosaic_rows"] == 1
    source_ids = {r.raw_row.row_id.value for r in source.row_inputs}
    output_ids = [r["source_row_id"] for c in report["candidates"] for r in c["source_rows"]]
    output_ids += [r["source_row_id"] for r in report["excluded_rows"]]
    assert len(output_ids) == len(set(output_ids)) == len(source_ids)
    assert set(output_ids) == source_ids
    rectangles = [c for c in report["candidates"] if c["geometry_kind"] == "RECTANGLE"]
    assert all(len(c["source_rows"]) == 1 for c in rectangles)
    assert all(c["rectangle"]["grid_status"] == "NOT_GENERATED" for c in rectangles)


@pytest.mark.parametrize("field,value", [
    ("Req. Ang. Res.", "3.0"), ("Ref.Frequency", "94.0"),
    ("Freq SPW 1", "104.0"), ("RA", "301.0"), ("Use TP?", "False"),
])
def test_custom_never_borrows_other_setup_request_or_reference(field, value):
    def edit(rows):
        row = next(r for r in rows if r["Mosaic"] == "Custom")
        assert field in row
        row[field] = value
    assert len(custom(reconstruct_queue_mosaics(parsed(edit)))) == 2


def test_offset_is_east_north_and_raw_evidence_is_unchanged():
    def edit(rows):
        for r in rows:
            if r["Mosaic"] == "Custom":
                r.update(RA="359.999", Dec="0", **{"Long Offset": "7.2", "Lat Offset": "0"})
    source = parsed(edit)
    before = tuple(r.raw_row for r in source.row_inputs)
    group, = custom(reconstruct_queue_mosaics(source))
    for r in group["source_rows"]:
        assert r["center"]["icrs_deg"] == pytest.approx([.001, 0], abs=1e-10)
        assert r["center"]["status"] == "DIAGNOSTIC_ONLY"
    assert before == tuple(r.raw_row for r in source.row_inputs)
    # Equal positions remain separate source records, not extra inferred depth.
    assert len(group["source_rows"]) == 2 and group["unique_offset_count"] == 1


def test_galactic_rectangle_is_preserved_without_guessing_reference_frame():
    def edit(rows):
        r = next(r for r in rows if r["Mosaic"] == "Rectangle")
        r.update(RA="34.7185", Dec="-0.465", **{"Mos. Coord.": "galactic", "Long Offset": "30"})
    report = reconstruct_queue_mosaics(parsed(edit))
    c = next(c for c in report["candidates"] if c["rectangle"] and c["rectangle"]["frame_raw"] == "galactic")
    assert c["source_rows"][0]["center"]["icrs_deg"] is None
    assert c["source_rows"][0]["center"]["reasons"] == ["GALACTIC_REFERENCE_FRAME_UNVERIFIED"]
    assert c["rectangle"]["pa_convention"] == "OT_P_SIDE_FROM_HORIZONTAL_SIGN_NOT_VERIFIED"


@pytest.mark.parametrize("dx,dy,expected", [
    (36, 0, [10.01, 0]), (-36, 0, [9.99, 0]),
    (0, 36, [10, .01]), (0, -36, [10, -.01]),
])
def test_rectangle_center_offsets_follow_sky_axes_not_screen_axes(dx, dy, expected):
    def edit(rows):
        r = next(r for r in rows if r["Mosaic"] == "Rectangle")
        r.update(RA="10", Dec="0", **{"Long Offset": str(dx), "Lat Offset": str(dy),
                                       "Mos. PA": "90"})
    report = reconstruct_queue_mosaics(parsed(edit))
    c = next(c for c in report["candidates"] if c["group"]["target_name"] == "MC35")
    assert c["source_rows"][0]["center"]["icrs_deg"] == pytest.approx(expected)
    assert c["rectangle"]["pa_deg"] == 90  # PA does not rotate the centre offset.


def test_incomplete_or_foreign_source_is_rejected_and_order_is_deterministic():
    source = parsed()
    with pytest.raises(ValueError, match="Complete Queue"):
        reconstruct_queue_mosaics(replace(source, status=QueueParseStatus.ERROR))
    with pytest.raises(ValueError, match="parsed snapshot"):
        reconstruct_queue_mosaics(replace(source, snapshot=replace(source.snapshot, snapshot_sha256="0"*64)))
    assert reconstruct_queue_mosaics(source) == reconstruct_queue_mosaics(
        replace(source, row_inputs=tuple(reversed(source.row_inputs))))


def test_cli_writes_report_without_overwriting_input_or_existing_output(tmp_path):
    out = tmp_path / "audit.json"
    args = ["--queue-csv", str(FIXTURE), "--output", str(out)]
    assert main(args) == 0
    original = out.read_bytes()
    assert json.loads(original)["scientific_status"] == "NOT_EVALUATED"
    assert main(args) == 2
    assert out.read_bytes() == original
    bad = tmp_path / "bad.csv"
    bad.write_text("bad input")
    assert main(["--queue-csv", str(bad), "--output", str(tmp_path / "missing.json")]) == 2
    assert not (tmp_path / "missing.json").exists()
