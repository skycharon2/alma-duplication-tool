"""Operational standalone evidence, Portal fallback and independent scope gates."""

from itertools import product
import json

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_row_beam import resolve_queue_primary_beam_diameter
from alma_duplicate.rules.queue_common import evaluate_queue_common
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_search_plan_spatial import validation
from tests.unit.test_queue_csv_parser import _records, _indices, _render

ABSENT = object()


def source(standalone=ABSENT, use7="False", tp="False", changes=None):
    records = _records()[:42]
    columns = _indices(records)
    row = records[41]
    for k, v in (
        {
            "RA": "10",
            "Dec": "20",
            "Long Offset": "0",
            "Lat Offset": "0",
            "Use 7-m?": use7,
            "Use TP?": tp,
            "Ref.Frequency": "338.5",
        }
        | (changes or {})
    ).items():
        row[columns[k]] = v
    if standalone is not ABSENT:
        records[39].append("standAlone_ACA")
        records[40].append("")
        row.append(standalone)
    return _render(records)


def evaluate(raw):
    q = parse_queue_csv_bytes(raw)
    assert q.can_reconstruct, q.issues
    s = search_candidates(validation(sources=("QUEUE",), ra=10, dec=20), queue_result=q)
    c = s.queue.retained_rows[0]
    return s, evaluate_queue_common(
        s.plan.validation.request, c.context, c.spatial_evidence
    )


@pytest.mark.parametrize("use7,tp", list(product(("True", "False"), repeat=2)))
@pytest.mark.parametrize("standalone", [ABSENT, "True", "False"])
def test_operational_priority_and_absent_flags(standalone, use7, tp):
    row = parse_queue_csv_bytes(source(standalone, use7, tp)).row_inputs[0]
    beam = resolve_queue_primary_beam_diameter(row)
    if standalone == "True":
        expected = (7.0, 12.0) if tp == "True" else (7.0,)
    else:
        expected = (7.0, 12.0) if use7 == "True" else (12.0,)
    assert beam.diameters_m == expected
    assert beam.standalone is (None if standalone is ABSENT else standalone == "True")
    assert ("STANDALONE_WITHOUT_7M_REQUEST" in beam.anomalies) == (standalone == "True" and use7 == "False")
    details = dict(beam.details(row))
    assert details["use_7m_requested"] == use7.lower()
    assert details["use_tp_requested"] == tp.lower()
    assert len(details) == len(beam.details(row))


@pytest.mark.parametrize("token", ["", "unknown", "1", "0", "NaN"])
def test_invalid_present_value_never_uses_missing_fallback(token):
    _, (_, p) = evaluate(source(token))
    assert p.outcome is None
    assert dict(p.derived)["antenna_diameter_m"] is None
    assert dict(p.details)["standalone_aca_field"] == "INVALID"
    assert "INVALID_STANDALONE_VALUE" in p.reasons


def test_seven_metre_beam_is_wider_and_inclusive(monkeypatch):
    from alma_duplicate.primary_beam import primary_beam_fwhm_deg

    radius12 = primary_beam_fwhm_deg(338.5, 12) / 2
    monkeypatch.setattr(
        "alma_duplicate.rules.queue_common.angular_separation_deg", lambda *a: radius12 * 1.2
    )
    assert evaluate(source("False"))[1][1].outcome == "NOT_SATISFIED"
    p7 = evaluate(source("True"))[1][1]
    assert p7.outcome == "SATISFIED"
    assert dict(p7.derived)["candidate_radius_deg"] == pytest.approx(radius12 * 12 / 7)
    for factor, expected in [
        (1 - 1e-12, "SATISFIED"),
        (1, "SATISFIED"),
        (1 + 1e-12, "NOT_SATISFIED"),
    ]:
        monkeypatch.setattr(
            "alma_duplicate.rules.queue_common.angular_separation_deg",
            lambda *a: dict(p7.derived)["candidate_radius_deg"] * factor,
        )
        assert evaluate(source("True"))[1][1].outcome == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"Mosaic": "Custom"},
        {"RA": "0", "Dec": "0"},
        {"Mos. Coord.": "B1950"},
        {"Long Offset": "400000"},
    ],
)
def test_non_array_blockers_remain(changes):
    _, (_, p) = evaluate(source(changes=changes))
    assert p.outcome is None


def test_offset_transport_with_tp_requested():
    _, (_, p) = evaluate(
        source(changes={"Mosaic": "N/A", "Long Offset": "3", "Lat Offset": "4"})
    )
    assert p.outcome == "SATISFIED"
    assert dict(p.derived)["separation_deg"] * 3600 == pytest.approx(5, abs=1e-6)


def test_duplicate_and_unknown_columns_still_rejected():
    import csv, io

    for name in ("standAlone_ACA", "unrelated_column"):
        records = list(csv.reader(io.StringIO(source("True").decode())))
        records[39].append(name)
        records[40].append("")
        records[41].append("True")
        assert not parse_queue_csv_bytes(_render(records)).can_reconstruct


def test_cross_source_spatial_evidence_rejected():
    s, _ = evaluate(source())
    other, _ = evaluate(source("True"))
    c = s.queue.retained_rows[0]
    with pytest.raises(ValueError, match="another context"):
        evaluate_queue_common(
            s.plan.validation.request,
            c.context,
            other.queue.retained_rows[0].spatial_evidence,
        )


def test_same_row_interpretation_reaches_continuum():
    from tests.integration.test_queue_continuum import case

    _, _, c = case({"Use 7-m?": "True", "Use TP?": "True"})
    assert len(c.beam_variants) == 2
    assert all(next(r for r in v.evaluation.criteria if r.criterion_id == "POS-SINGLE").outcome
               == "SATISFIED" for v in c.beam_variants)
    assert c.branches[0].status == "CRITERIA_MET"


def test_legacy_candidate_profile_stays_conservative():
    from alma_duplicate.queue_position import candidate_diameter

    row = queue_rows({"Use 7-m?": "True", "Use TP?": "True"}).row_inputs[0]
    assert candidate_diameter(row)[0] is None
    assert resolve_queue_primary_beam_diameter(row).diameters_m == (7.0, 12.0)


def test_cli_reads_optional_field_and_exports_assumption(tmp_path):
    from alma_duplicate.cli.evaluate import main
    from tests.integration.test_queue_candidate_beam import REQUEST

    p = json.loads(REQUEST.read_text())
    p["request"]["position"].update(ra=10, dec=20, ra_format="DEG", dec_format="DEG")
    p["search_options"]["sources"] = ["QUEUE"]
    request = tmp_path / "request.json"
    request.write_text(json.dumps(p))
    for token in (ABSENT, "True", ""):
        csv = tmp_path / "queue.csv"
        csv.write_bytes(source(token))
        out = tmp_path / "report.json"
        assert (
            main(
                [
                    "--request",
                    str(request),
                    "--queue-csv",
                    str(csv),
                    "--queue-common",
                    "--output",
                    str(out),
                    "--overwrite",
                ]
            )
            == 0
        )
        doc = json.loads(out.read_text())
        result = next(
            r
            for r in doc["context_evaluations"][0]["criteria"]
            if r["criterion_id"] == "POS-SINGLE"
        )
        assert result["method_version"] == "queue_pos_single_6"
        assert dict(result["details"])["standalone_aca_field"] == (
            "ABSENT" if token is ABSENT else "INVALID" if token == "" else "PRESENT"
        )


def test_legacy_beam_search_cannot_drop_new_seven_metre_candidate():
    q = parse_queue_csv_bytes(source("True", use7="False", tp="False"))
    v = validation(sources=("QUEUE",), ra=10, dec=20 + 10 / 3600)
    s = search_candidates(v, queue_result=q, queue_candidate_beam=True)
    assert len(s.queue.retained_rows) == 1
    c = s.queue.retained_rows[0]
    p = evaluate_queue_common(v.request, c.context, c.spatial_evidence)[1]
    assert p.outcome == "SATISFIED"
