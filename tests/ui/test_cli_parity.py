"""Form/CLI agreement using pinned inputs under the current UI configuration.

Historical catalog runs remain independently checked by test_reports. These
runs use exported form requests (including UI sensitivity IDs) and explicit
formal Queue flags, rather than pretending legacy catalog options are UI options.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.cli.acceptance import load_catalog
from alma_duplicate.cli.evaluate import main as evaluate_main
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui import create_app
from alma_duplicate.ui import runs

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "examples/acceptance/catalog.json"
CASE_IDS = [case["case_id"] for case in json.loads(CATALOG.read_text())["cases"]]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import requests
    from alma_duplicate.clients.archive_client import ArchiveClient

    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *a, **k: pytest.fail("parity must not access the network"))
    original = ArchiveClient.__init__

    def replay_only(self, *args, **kwargs):
        assert kwargs.get("executor") is not None, "live Archive client constructed"
        original(self, *args, **kwargs)

    monkeypatch.setattr(ArchiveClient, "__init__", replay_only)


@pytest.fixture(scope="module")
def cases():
    # Verify request, source, reference and captured-response checksums.
    _, loaded = load_catalog(CATALOG)
    return {case["case_id"]: (case, inputs) for case, inputs, _ in loaded}


def form_for(document):
    """Translate only the catalog's supported form fields, preserving units/bindings."""
    q, search = document["request"], document["search_options"]
    assert q["target_kind"] == "FIXED" and q["geometry"] == "SINGLE_POINTING"
    assert search.get("predicates", []) == []
    assert q["position"]["frame"] == "ICRS"
    data = MultiDict({"action": "assess", "setup_id": q["setup_id"],
                      "target_name": q.get("target_name", ""),
                      "redshift": str(q.get("source_redshift", ""))})
    for name in ("ra", "dec", "ra_format", "dec_format"):
        data[name] = str(q["position"][name])
    data.setlist("intents", q["intents"])
    data.setlist("sources", search["sources"])
    if q["setup_complete"]:
        data["setup_complete"] = "on"
    if "result_limit" in search:
        data["result_limit"] = str(search["result_limit"])

    def quantity(name, value):
        if value is not None:
            data[name], data[name + "_unit"] = str(value["value"]), value["unit"]

    def frequency(name, value):
        if value is not None:
            assert value["frame"] == "UNKNOWN"
            quantity(name, value)
            data[name + "_kind"] = value["kind"]

    quantity("angular", q.get("angular_resolution"))
    quantity("radius", search.get("radius"))
    frequency("representative", q.get("representative_frequency"))
    windows = {}
    for i, window in enumerate(q["spectral_windows"]):
        assert "interval" not in window
        row = f"w{i:012x}"
        windows[window["window_id"]] = row
        data.add("rows", row)
        data[row + "_id"] = window["window_id"]
        frequency(row + "_center", window.get("center"))
        quantity(row + "_bandwidth", window.get("bandwidth"))
        data[row + "_bandwidth_kind"] = window.get("bandwidth_kind", "UNKNOWN")
        data[row + "_mode"] = window.get("correlator_mode", "UNKNOWN")
    seen = set()
    for sensitivity in q["sensitivities"]:
        if sensitivity["purpose"] == "CONTINUUM":
            assert sensitivity["scope"] == "SETUP" and sensitivity["basis"] == "AGGREGATE"
            assert sensitivity["aggregate_path"] == "DIRECT_DECLARATION"
            assert "aggregate" not in seen
            seen.add("aggregate")
            quantity("aggregate", sensitivity.get("rms"))
            data.setlist("aggregate_windows", sensitivity["window_ids"])
        else:
            assert sensitivity["purpose"] == "LINE" and sensitivity["scope"] == "WINDOW"
            assert sensitivity["basis"] == "SMOOTHED" and len(sensitivity["window_ids"]) == 1
            row = windows[sensitivity["window_ids"][0]]
            assert row not in seen
            seen.add(row)
            quantity(row + "_rms", sensitivity.get("rms"))
            quantity(row + "_resolution", sensitivity.get("smoothing_resolution"))
    return data


def normalized_times(document):
    """Only four explicit execution-time paths; capture dates remain compared."""
    result = deepcopy(document)
    for key in ("generated_at", "search_started_at", "search_finished_at"):
        if key in result and result[key] is not None:
            datetime.fromisoformat(result[key])
            result[key] = "<execution time>"
    snapshot = (result.get("sources", {}).get("QUEUE", {}).get("source_metadata") or {}).get("snapshot")
    if snapshot is not None and "parsed_at" in snapshot:
        datetime.fromisoformat(snapshot["parsed_at"])
        snapshot["parsed_at"] = "<execution time>"
    return result


def assert_same_report(browser, cli, request_bytes):
    # The only non-time difference is the actual input-file provenance.
    assert browser["input_sha256"] is None
    assert cli["input_sha256"] == hashlib.sha256(request_bytes).hexdigest()
    expected = normalized_times(cli)
    expected["input_sha256"] = None
    assert normalized_times(browser) == expected
    assert inspect_report(browser, inspection_version="3") == inspect_report(cli, inspection_version="3")


def cli_run(tmp_path, request_bytes, inputs, *, suffix=""):
    request_path = tmp_path / f"request{suffix}.json"
    output = tmp_path / f"report{suffix}.json"
    request_path.write_bytes(request_bytes)
    document = json.loads(request_bytes)
    args = ["--request", str(request_path), "--output", str(output)]
    for key, flag in (("archive_replay", "--archive-replay"), ("queue_csv", "--queue-csv")):
        if key in inputs:
            args += [flag, str(inputs[key])]
    # Independently express the public UI's documented configuration.
    if "QUEUE" in document["search_options"]["sources"]:
        args.append("--queue-common")
        for intent, flag in (("LINE", "--queue-line"), ("CONTINUUM", "--queue-continuum")):
            if intent in document["request"]["intents"]:
                args.append(flag)
    code = evaluate_main(args)
    return code, json.loads(output.read_bytes())


def run_form_parity(tmp_path, monkeypatch, inputs, data, expected_code):
    completed = []
    original = runs.assess_observation

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        completed.append(report_json_text(result.document).encode())
        return result

    monkeypatch.setattr(runs, "assess_observation", capture)
    client = create_app({
        "TESTING": True, "REPORT_DIRECTORY": None,
        "OFFLINE_ARCHIVE_REPLAY": inputs.get("archive_replay"),
        "OFFLINE_QUEUE_CSV": inputs.get("queue_csv"),
    }).test_client()
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    assert len(completed) == 1
    url = response.location
    request_bytes = client.get(url + "/download/request").data
    raw = client.get(url + "/download/report").data
    assert raw == completed[0]
    document = json.loads(raw)
    code, cli = cli_run(tmp_path, request_bytes, inputs)
    assert code == expected_code
    assert_same_report(document, cli, request_bytes)
    inspection_bytes = client.get(url + "/download/inspection").data
    assert json.loads(inspection_bytes) == inspect_report(cli, inspection_version="3")
    contexts = document["context_evaluations"]
    for page in range(1, max(1, (len(contexts) + 19) // 20) + 1):
        html = client.get(url + f"?page={page}&view=all").get_data(as_text=True)
        assert "NOT_AGGREGATED" in html
        for context in contexts[(page - 1) * 20:page * 20]:
            assert context["context_id"] in html
        assert client.get(url + "/download/report").data == raw
        assert client.get(url + "/download/inspection").data == inspection_bytes
        assert client.get(url + "/download/request").data == request_bytes
    assert len(completed) == 1, "refresh/pagination/export reran assessment"
    return document, client, url


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_catalog_form_cli_parity(tmp_path, monkeypatch, cases, case_id):
    case, inputs = cases[case_id]
    data = form_for(json.loads(inputs["request"].read_bytes()))
    run_form_parity(tmp_path, monkeypatch, inputs, data, case["expected_exit_code"])


@pytest.mark.parametrize('width,unit,outcome', [
    ('2', 'GHz', 'SATISFIED'), ('2000', 'MHz', 'SATISFIED'),
    ('1875', 'MHz', 'SATISFIED'), ('1800', 'MHz', 'NOT_SATISFIED'),
    ('2100', 'MHz', None),
])
def test_proposed_nominal_mapping_form_cli_and_both_sources(tmp_path, monkeypatch, cases, width, unit, outcome):
    _, inputs = cases['dual-source-continuum']
    data = form_for(json.loads(inputs['request'].read_bytes()))
    for row in data.getlist('rows'):
        data[row + '_bandwidth'] = width
        data[row + '_bandwidth_unit'] = unit
        data[row + '_bandwidth_kind'] = 'NOMINAL'
    document, client, url = run_form_parity(tmp_path, monkeypatch, inputs, data, 0)
    setup = document['request_criteria'][0]
    assert setup['method_version'] == 'continuum_setup_4'
    assert setup['approval'] == 'APPROVED' and setup['outcome'] == outcome
    assert document['evaluation_configuration']['nominal_conversion'] == 'PORTAL_SCRIPT_V1'
    assert {c['reference']['source'] for c in document['context_evaluations']} == {'ARCHIVE', 'QUEUE'}
    if outcome == 'SATISFIED':
        for source in ('ARCHIVE', 'QUEUE'):
            assert any(c['reference']['source'] == source and c['branches'][0]['status'] == 'CRITERIA_MET'
                       for c in document['context_evaluations'])
    elif outcome is None:
        assert all(c['branches'][0]['status'] != 'CRITERIA_MET' for c in document['context_evaluations'])
    html = client.get(url).get_data(as_text=True).split('<details id="technical-records"')[0]
    assert 'Proposed window bandwidth qualification' in html
    assert 'NOMINAL' in html
    if outcome == 'SATISFIED':
        assert '1.875' in html
    exported = client.get(url + '/download/request').get_json()['request']
    assert all(w['bandwidth_kind'] == 'NOMINAL' and w['bandwidth']['value'] == width
               for w in exported['spectral_windows'])


@pytest.mark.parametrize("variant", ["dual-mixed", "declaration", "declaration-conflict", "equivalent-units"])
def test_additional_form_contracts(tmp_path, monkeypatch, cases, variant):
    case_id = "dual-source-continuum" if variant.startswith("declaration") else "dual-source-line"
    _, inputs = cases[case_id]
    data = form_for(json.loads(inputs["request"].read_bytes()))
    if variant.startswith("declaration"):
        data.setlist("rows", [])
        data.setlist("aggregate_windows", [])
        data.pop("setup_complete", None)
        data["continuum_setup_declaration"] = "on"
        if variant == "declaration-conflict":
            data["setup_complete"] = "on"
    elif variant == "dual-mixed":
        data.setlist("intents", ["LINE", "CONTINUUM"])
        data.update({"representative": "230", "aggregate": "0.1"})
    else:
        replacements = {"w000000000000_center": "230538", "w000000000000_center_unit": "MHz",
                     "w000000000000_resolution": "20000", "w000000000000_resolution_unit": "m/s",
                     "w000000000000_rms": "0.0003", "w000000000000_rms_unit": "Jy/beam",
                        "angular": "300", "angular_unit": "mas"}
        for key, value in replacements.items():
            data[key] = value
    document, _, _ = run_form_parity(tmp_path, monkeypatch, inputs, data, 0)
    if variant == "dual-mixed":
        assert {b["branch"] for c in document["context_evaluations"] for b in c["branches"]} == {"LINE", "CONTINUUM"}
    elif variant == "declaration-conflict":
        assert "CONTINUUM_SETUP_DECLARATION_CONFLICT" in document["request_criteria"][0]["reasons"]


def test_pagination_keeps_all_evaluations_and_exact_downloads(tmp_path, monkeypatch, cases):
    import csv
    import io

    _, inputs = cases["dual-source-line"]
    lines = inputs["queue_csv"].read_text().splitlines(keepends=True)
    header = next(i for i, line in enumerate(lines) if line.startswith("Project Code,Target Name,"))
    reader = list(csv.reader(lines[header:]))
    output = io.StringIO()
    output.write("".join(lines[:header]))
    writer = csv.writer(output)
    writer.writerows(reader[:2])  # Retain the original column and unit declarations.
    for index in range(21):
        row = reader[2].copy()
        row[1] = f"Synthetic pagination target {index}"
        writer.writerow(row)
    queue = tmp_path / "pagination.csv"
    queue.write_text(output.getvalue())
    data = form_for(json.loads(inputs["request"].read_bytes()))
    data.setlist("sources", ["QUEUE"])
    doc, client, url = run_form_parity(tmp_path, monkeypatch, {"queue_csv": queue}, data, 0)
    assert len(doc["context_evaluations"]) == 21
    assert doc["evaluation_scope"]["shown_candidates"] == 1
    assert doc["evaluation_scope"]["display_truncated"] is True
    first = client.get(url).get_data(as_text=True)
    second = client.get(url + "?page=2").get_data(as_text=True)
    assert 'id="context-19"' in first and 'id="context-20"' not in first
    assert 'id="context-20"' in second and 'id="context-0"' not in second
    assert "Next" in first and "Previous" in second
    assert client.get(url + "?page=3").status_code == 404


def test_solar_adapter_cli_and_viewer_parity_without_source_access(tmp_path, monkeypatch):
    from alma_duplicate.clients.archive_replay import RecordedArchiveClient
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient

    def forbidden(*args, **kwargs):
        pytest.fail("Solar exemption accessed a source")

    monkeypatch.setattr(RecordedArchiveClient, "__init__", forbidden)
    monkeypatch.setattr(QueueCsvClient, "load", forbidden)
    wire = {"request": {"target_kind": "SUN", "geometry": "SINGLE_POINTING",
                        "setup_id": "solar", "intents": ["CONTINUUM"]},
            "search_options": {"sources": ["ARCHIVE", "QUEUE"]}}
    inputs = {"archive_replay": tmp_path / "must-not-open.json", "queue_csv": tmp_path / "must-not-open.csv"}
    result = runs.BrowserAssessment(inputs["archive_replay"], inputs["queue_csv"]).assess(wire)
    assert str(result.status) == "SOLAR_EXEMPTION"
    request_bytes = report_json_text(wire).encode()
    code, cli = cli_run(tmp_path, request_bytes, inputs)
    assert code == 0
    assert_same_report(result.document, cli, request_bytes)
    # Solar is an execution-adapter/viewer boundary test, not a supported form mode.
    case = tmp_path / "viewer" / "solar"
    case.mkdir(parents=True)
    raw = report_json_text(result.document).encode()
    (case / "report.json").write_bytes(raw)
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": case.parent,
                         "OFFLINE_ARCHIVE_REPLAY": None, "OFFLINE_QUEUE_CSV": None}).test_client()
    assert b"Solar exemption: search not performed" in client.get("/reports/1").data
    assert client.get("/reports/1/download/report").data == raw
    assert client.get("/reports/1/download/inspection").get_json() == inspect_report(cli, inspection_version="3")


def test_comparison_exceptions_do_not_hide_science_or_provenance():
    base = {"generated_at": "2026-09-30T10:00:00+00:00",
            "sources": {"QUEUE": {"source_metadata": {"snapshot": {
                "parsed_at": "2026-09-30T10:00:00+00:00", "sha256": "snapshot-digest"}}}},
            "method_version": "method_2", "outcome": "SATISFIED",
            "capture_started_at": "2026-09-20T10:00:00+00:00",
            "pair_reference": {"window_id": "line-0", "spw_number": 0},
            "unknown_future_evidence": {"parsed_at": "scientifically-relevant-value"}}
    for key, changed in (("method_version", "method_1"), ("outcome", "NOT_SATISFIED"),
                         ("capture_started_at", "2026-09-21T10:00:00+00:00"),
                         ("pair_reference", {"window_id": "line-1", "spw_number": 0}),
                         ("unknown_future_evidence", {"parsed_at": "changed"})):
        other = deepcopy(base)
        other[key] = changed
        assert normalized_times(base) != normalized_times(other)
    other = deepcopy(base)
    other["sources"]["QUEUE"]["source_metadata"]["snapshot"]["sha256"] = "different-snapshot"
    assert normalized_times(base) != normalized_times(other)
