from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_mode_census import main
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_mode_census import build_census, mode_counts, run_census

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def fixture_variant(changes):
    rows = list(csv.reader(io.StringIO(FIXTURE.read_text())))
    columns = {name: i for i, name in enumerate(rows[39])}
    for name, value in changes.items():
        rows[41][columns[name]] = value
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    return stream.getvalue().encode()


def test_all_physical_spws_preserve_provenance_and_no_sps_expansion(tmp_path):
    result = run_census(FIXTURE, tmp_path / "census")
    records = list(csv.DictReader((tmp_path / "census/spws.csv").open()))
    raw = QueueCsvClient().load(FIXTURE)
    # Count directly from raw fields, independently of the typed SPW list.
    expected = {
        (row.row_id.value, str(n))
        for row in raw.raw_rows
        for n in range(1, 17)
        if row.value(f"Freq SPW {n}").strip()
    }
    assert {(r["source_row_id"], r["spw_number"]) for r in records} == expected
    assert len(records) == result["denominator"]["regular_spws"]
    assert result["denominator"]["spectral_scan_rows_excluded"] == 1
    assert result["denominator"]["raw_rows"] == 13
    assert not result["snapshot"]["matches_repository_pinned_snapshot"]
    assert all(r["method_status"] == "PROVISIONAL" for r in records)
    assert all(r["source_bound_mode"] == "UNKNOWN" for r in records)
    for key in (
        "conditional_unique_configuration",
        "conditional_mode_consensus",
        "reference_only_mode_consensus",
        "source_bound",
    ):
        assert sum(result[key][m] for m in ("FDM", "TDM", "UNKNOWN")) == len(records)
    for name, digest in result["artifacts_sha256"].items():
        assert (
            hashlib.sha256((tmp_path / "census" / name).read_bytes()).hexdigest()
            == digest
        )
    assert sum(
        r["count"] for r in csv_to_json_signatures(tmp_path / "census/signatures.csv")
    ) == len(records)


def csv_to_json_signatures(path):
    return [{**r, "count": int(r["count"])} for r in csv.DictReader(path.open())]


def test_mixed_modes_are_not_propagated_across_a_row():
    data = fixture_variant(
        {
            "Polarization": "DOUBLE",
            "Bandwidth SPW 1": "1875",
            "Spec.Res. SPW 1": "31.25",
            "Bandwidth SPW 2": "1875",
            "Spec.Res. SPW 2": "7.81201171875",
            "Bandwidth SPW 3": "1875",
            "Spec.Res. SPW 3": "3.14159",
        }
    )
    parsed = parse_queue_csv_bytes(data)
    _, records, _, _ = build_census(parsed)
    first = [r for r in records if r["source_ordinal"] == 0]
    assert [r["conditional_mode_consensus"] for r in first[:3]] == [
        "TDM",
        "FDM",
        "UNKNOWN",
    ]
    assert first[1]["reference_only_mode_consensus"] == "UNKNOWN"
    assert first[1]["export_compatibility_only"]


def test_array_flags_are_retained_but_cannot_supply_processor():
    parsed = parse_queue_csv_bytes(
        fixture_variant({"Use 7-m?": "False", "Use TP?": "False"})
    )
    _, records, _, _ = build_census(parsed)
    first = records[0]
    assert not first["use_7m"] and not first["use_tp"]
    assert first["processor"] == "UNRESOLVED"
    assert first["source_bound_mode"] == "UNKNOWN"


@pytest.mark.parametrize(
    "changes",
    [
        {"Spec.Res. SPW 1": ""},
        {"Spec.Res. SPW 1": "NaN"},
        {"Bandwidth SPW 1": "-5"},
        {"RA": "400"},
    ],
)
def test_rejected_rows_do_not_vanish_from_success_denominator(
    changes, tmp_path, capsys
):
    source = tmp_path / "bad.csv"
    source.write_bytes(fixture_variant(changes))
    assert (
        main(["--queue-csv", str(source), "--output-dir", str(tmp_path / "report")])
        == 2
    )
    assert "incomplete" in capsys.readouterr().err
    assert not (tmp_path / "report").exists()


def test_pinned_guard_cannot_mistake_small_fixture_for_full_snapshot(tmp_path):
    assert (
        main(
            [
                "--queue-csv",
                str(FIXTURE),
                "--output-dir",
                str(tmp_path / "report"),
                "--require-pinned-snapshot",
            ]
        )
        == 2
    )
    assert not (tmp_path / "report").exists()


def test_repeat_output_is_identical_and_previous_output_is_not_replaced(tmp_path):
    a = run_census(FIXTURE, tmp_path / "one")
    b = run_census(FIXTURE, tmp_path / "two")
    assert a == b
    for path in (tmp_path / "one").iterdir():
        assert path.read_bytes() == (tmp_path / "two" / path.name).read_bytes()
    before = (tmp_path / "one/summary.json").read_bytes()
    assert (
        main(["--queue-csv", str(FIXTURE), "--output-dir", str(tmp_path / "one")]) == 2
    )
    assert (tmp_path / "one/summary.json").read_bytes() == before


def test_empty_and_sps_only_denominators_have_no_success_percentage():
    assert mode_counts([])["unique_percent"] is None
    parsed = QueueCsvClient().load(FIXTURE)
    sps = tuple(r for r in parsed.row_inputs if not hasattr(r.spectral, "spws"))
    summary, records, signatures, configs = build_census(
        replace(parsed, row_inputs=sps, raw_rows=tuple(r.raw_row for r in sps))
    )
    assert summary["denominator"]["regular_spws"] == 0
    assert summary["conditional_mode_consensus"]["unique_percent"] is None
    assert records == signatures == configs == []


def test_cli_summary_is_explicitly_conditional_and_json_is_strict(tmp_path, capsys):
    assert (
        main(["--queue-csv", str(FIXTURE), "--output-dir", str(tmp_path / "report")])
        == 0
    )
    stdout = capsys.readouterr().out
    assert "conditional_unique_configuration" in stdout
    assert "source_bound" in stdout
    assert "not source-bound" in stdout
    report = json.loads(
        (tmp_path / "report/summary.json").read_text(),
        parse_constant=lambda value: pytest.fail(value),
    )
    assert report["evidence_origin"] == "APPLICATION_DERIVED"
