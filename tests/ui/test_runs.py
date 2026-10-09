"""Execute real offline assessments through the form and retain exact artifacts."""

import hashlib
import json
from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.reporting import report_json_text
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.ui import create_app
from alma_duplicate.ui import runs as execution

ROOT = Path(__file__).parents[2]
ROW = "w123456abcdef"


def line_form():
    return MultiDict({
        "rows": ROW, "setup_id": "setup-1", "setup_complete": "on",
        "target_name": "Offline LINE check", "ra": "201.365", "dec": "-43.019",
        "radius": "30", "sources": "ARCHIVE", "intents": "LINE", "angular": "0.3",
        "redshift": "0.024", ROW + "_id": "line-0", ROW + "_center": "230.538",
        ROW + "_center_kind": "REST", ROW + "_mode": "FDM",
        ROW + "_resolution": "20", ROW + "_rms": "0.3", "result_limit": "1", "action": "assess",
    })


def config(**overrides):
    return {
        "TESTING": True, "REPORT_DIRECTORY": None,
        "OFFLINE_ARCHIVE_REPLAY": ROOT / "examples/confirmed_line/archive/manifest.json",
        "OFFLINE_QUEUE_CSV": ROOT / "examples/acceptance/queue/dual-source-line.csv",
        "LIVE_ARCHIVE": False,
    } | overrides


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    from alma_duplicate.clients.archive_client import ArchiveClient
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("live network access"))
    # Replays supply an executor; the default live executor is forbidden here.
    original = ArchiveClient.__init__

    def checked_init(self, *args, **kwargs):
        assert kwargs.get("executor") is not None
        original(self, *args, **kwargs)

    monkeypatch.setattr(ArchiveClient, "__init__", checked_init)


@pytest.mark.parametrize("purposes", [["LINE"], ["CONTINUUM"], ["LINE", "CONTINUUM"]])
def test_real_dual_source_run_retains_exact_report_and_input(monkeypatch, purposes):
    captured = []
    original = execution.assess_observation

    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        captured.append((kwargs["options"], report_json_text(result.document).encode()))
        return result

    monkeypatch.setattr(execution, "assess_observation", observe)
    data = line_form()
    data.setlist("sources", ["ARCHIVE", "QUEUE"])
    data.setlist("intents", purposes)
    if "CONTINUUM" in purposes:
        data.update({"representative": "230", "aggregate": "0.1", "aggregate_windows": "line-0"})
        if purposes == ["CONTINUUM"]:
            # Same Guide A reference cone with two explicitly usable windows.
            data.setlist("rows", [ROW, "wabcdef123456"])
            data.setlist(ROW + "_center_kind", ["SKY"])
            data.setlist(ROW + "_center", ["226"])
            data.update({ROW + "_bandwidth": "1875", ROW + "_bandwidth_kind": "USABLE",
                         "wabcdef123456_id": "w1", "wabcdef123456_center": "228",
                         "wabcdef123456_bandwidth": "1875", "wabcdef123456_bandwidth_kind": "USABLE"})
            data.setlist("aggregate_windows", ["line-0", "w1"])
            del data[ROW + "_rms"]
            del data[ROW + "_resolution"]
    overrides = {}
    if purposes == ["CONTINUUM"]:
        overrides = {"OFFLINE_ARCHIVE_REPLAY": ROOT / "examples/confirmed_continuum/archive/manifest.json",
                     "OFFLINE_QUEUE_CSV": ROOT / "examples/queue_continuum/queue.csv"}
    client = create_app(config(**overrides)).test_client()
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    location = response.location
    assert location.startswith("/runs/")
    html = client.get(location).get_data(as_text=True)
    from tests.ui.test_reports import DefaultVisibleText
    visible = DefaultVisibleText()
    visible.feed(html)
    text = ' '.join(visible.text)
    assert "Download this run's input request" not in text
    assert 'Download complete original JSON' not in text
    assert 'Optional data exports' in text
    assert 'Criteria for this LINE pair' in text if 'LINE' in purposes else 'Candidate conditions' in text
    assert "Assessment run" in html and "SYNTHETIC" in html
    assert "Execution status: COMPLETED" in html
    assert "Effective evaluation configuration" in html
    report = client.get(location + "/download/report")
    assert report.data == captured[0][1]
    assert hashlib.sha256(report.data).hexdigest() in html
    doc = report.get_json()
    assert doc["report_version"] == "5" and doc["input_sha256"] is None
    for index, context in enumerate(doc['context_evaluations']):
        positive = any(b['status'] == 'CRITERIA_MET' and b['branch'] in purposes for b in context['branches'])
        assert (f'id="context-{index}"' in html) == positive
    assert len(doc["context_evaluations"]) > 1  # The display cap never drops contexts.
    assert all(doc["sources"][source]["status"] == "COMPLETED" for source in ("ARCHIVE", "QUEUE"))
    assert client.get(location + "/download/inspection").get_json() == inspect_report(doc, inspection_version="3")
    request_doc = client.get(location + "/download/request").get_json()
    assert request_doc["request"]["target_name"] == "Offline LINE check"
    assert request_doc["search_options"]["result_limit"] == 1
    options = captured[0][0]
    assert options.queue_common is True
    assert options.queue_line == ("LINE" in purposes)
    assert options.queue_continuum == ("CONTINUUM" in purposes)
    # No second call on refresh, pagination, or either export.
    assert client.get(location + "?page=1").status_code == 200
    assert client.get(location + "/download/report").data == report.data
    assert len(captured) == 1
    assert report.headers["Cache-Control"] == "no-store"
    assert client.get(location + "?page=0").status_code == 400
    assert client.get(location + "?page=999").status_code == 404
    assert client.get(location + "/download/other").status_code == 404
    assert client.get("/reports/1").status_code == 404


@pytest.mark.parametrize("changes", [{"ra": "invalid"}, {"radius": ""}, {ROW + "_rms": "-1"}])
def test_invalid_or_unready_input_never_invokes_assessment(monkeypatch, changes):
    monkeypatch.setattr(execution, "assess_observation", lambda *a, **k: pytest.fail("assessment invoked"))
    client = create_app(config()).test_client()
    data = line_form()
    for key, value in changes.items():
        data.setlist(key, [value])
    response = client.post("/proposed", data=data)
    assert response.status_code == 200
    assert b"Assessment was not run" in response.data
    assert b'value="230.538"' in response.data
    assert client.get("/runs/unknown").status_code == 404


def test_validation_download_and_disabled_mode_never_assess(monkeypatch):
    monkeypatch.setattr(execution, "assess_observation", lambda *a, **k: pytest.fail("assessment invoked"))
    client = create_app(config()).test_client()
    data = line_form()
    for action in ("validate", "download", "add"):
        data.setlist("action", [action])
        assert client.post("/proposed", data=data).status_code == 200
    client = create_app(config(OFFLINE_ARCHIVE_REPLAY=None, OFFLINE_QUEUE_CSV=None)).test_client()
    assert b'value="assess"' not in client.get("/proposed").data
    data.setlist("action", ["assess"])
    assert b"Assessment sources are not configured" in client.post("/proposed", data=data).data


@pytest.mark.parametrize("mode,failed_source", [("mismatch", "ARCHIVE"), ("missing-queue", "QUEUE"), ("bad-queue", "QUEUE")])
def test_source_failure_preserves_other_source_report(mode, failed_source):
    cfg = config()
    data = line_form()
    data.setlist("sources", ["ARCHIVE", "QUEUE"])
    if mode == "mismatch":
        data.setlist("radius", ["31"])
    elif mode == "missing-queue":
        cfg["OFFLINE_QUEUE_CSV"] = None
    else:
        cfg["OFFLINE_QUEUE_CSV"] = ROOT / "examples/acceptance/queue/queue-failed-archive-preserved.csv"
    client = create_app(cfg).test_client()
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    document = client.get(response.location + "/download/report").get_json()
    assert document["sources"][failed_source]["status"] in {"FAILED", "INCOMPLETE", "NOT_PROVIDED"}
    other = "QUEUE" if failed_source == "ARCHIVE" else "ARCHIVE"
    assert document["sources"][other]["status"] == "COMPLETED"
    assert b"SOURCES_UNAVAILABLE" in client.get(response.location).data


def test_provider_construction_error_preserves_form_without_report(tmp_path):
    client = create_app(config(OFFLINE_ARCHIVE_REPLAY=tmp_path / "missing.json")).test_client()
    response = client.post("/proposed", data=line_form())
    assert response.status_code == 200
    assert b"No report was created" in response.data
    assert b'value="230.538"' in response.data
    assert str(tmp_path).encode() not in response.data


def test_separate_runs_restart_and_count_retention():
    cfg = config(MAX_RETAINED_RUNS=2)
    client = create_app(cfg).test_client()
    data = line_form()
    first = client.post("/proposed", data=data).location
    original = client.get(first + "/download/report").data
    data.setlist(ROW + "_rms", ["0.7"])
    second = client.post("/proposed", data=data).location
    assert first != second
    assert client.get(first + "/download/report").data == original
    assert client.get(second + "/download/request").get_json()["request"]["sensitivities"][0]["rms"]["value"] == "0.7"
    assert create_app(cfg).test_client().get(second).status_code == 404
    assert client.post("/proposed", data=data).status_code == 303
    assert b"retention limit" in client.get(first).data
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200


def test_byte_budget_and_unselected_sources(monkeypatch):
    client = create_app(config(MAX_RETAINED_BYTES=1)).test_client()
    assert b"No report was created" in client.post("/proposed", data=line_form()).data
    monkeypatch.setattr(execution, "RecordedArchiveClient", lambda *a: pytest.fail("unselected source opened"))
    client = create_app(config(OFFLINE_ARCHIVE_REPLAY="not-used")).test_client()
    data = line_form()
    data.setlist("sources", ["QUEUE"])
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    document = client.get(response.location + "/download/report").get_json()
    assert document["sources"]["ARCHIVE"]["status"] == "NOT_SELECTED"


def test_partial_continuum_without_windows_can_run():
    data = MultiDict({"setup_id": "setup-1", "ra": "201.365", "dec": "-43.019",
                      "radius": "30", "sources": "ARCHIVE", "intents": "CONTINUUM",
                      "representative": "230", "aggregate": "0.1", "action": "assess"})
    client = create_app(config()).test_client()
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    document = client.get(response.location + "/download/report").get_json()
    assert client.get(response.location + "/download/request").get_json()["request"]["spectral_windows"] == []
    assert "INDETERMINATE" in json.dumps(document["context_evaluations"])


def test_declared_continuum_report_matches_cli_and_preserves_provenance(tmp_path):
    from alma_duplicate.cli.evaluate import main
    from alma_duplicate.domain.proposed_observation import CONTINUUM_SETUP_DECLARATION

    data = MultiDict({"setup_id": "setup-1", "ra": "201.365", "dec": "-43.019",
                      "radius": "30", "intents": "CONTINUUM", "angular": "0.3",
                      "representative": "230", "aggregate": "0.1",
                      "continuum_setup_declaration": "on", "action": "assess"})
    data.setlist("sources", ["ARCHIVE", "QUEUE"])
    archive = ROOT / "examples/confirmed_continuum/archive/manifest.json"
    queue = ROOT / "examples/queue_continuum/queue.csv"
    client = create_app(config(OFFLINE_ARCHIVE_REPLAY=archive, OFFLINE_QUEUE_CSV=queue)).test_client()
    response = client.post("/proposed", data=data)
    assert response.status_code == 303
    doc = client.get(response.location + "/download/report").get_json()
    req = client.get(response.location + "/download/request").get_json()
    criterion = doc["request_criteria"][0]
    assert criterion["method_version"] == "continuum_setup_declaration_1"
    assert criterion["outcome"] == "SATISFIED" and criterion["eligible_for_formal_aggregation"]
    assert dict(criterion["details"])["evidence_basis"] == "USER_DECLARED"
    assert req["request"]["continuum_setup_declaration"] == CONTINUUM_SETUP_DECLARATION
    assert req["request"]["spectral_windows"] == [] and req["request"]["setup_complete"] is False
    assert doc["request"]["normalized"]["continuum_setup_declaration"] == CONTINUUM_SETUP_DECLARATION
    assert b"continuum setup qualification uses a researcher declaration" in client.get(response.location).data
    assert any(c["branches"][0]["status"] == "CRITERIA_MET" for c in doc["context_evaluations"])
    path = tmp_path / "request.json"
    path.write_text(json.dumps(req))
    output = tmp_path / "report.json"
    assert main(["--request", str(path), "--archive-replay", str(archive),
                 "--queue-csv", str(queue), "--queue-continuum", "--output", str(output),
                 '--report-detail', 'matches']) == 0
    cli = json.loads(output.read_text())
    for key in ("request_criteria", "context_evaluations", "evaluation_configuration"):
        assert doc[key] == cli[key]
    # A complete empty list contradicts the declaration; validation itself is not a scientific verdict.
    data["setup_complete"] = "on"
    conflict = client.post("/proposed", data=data)
    result = client.get(conflict.location + "/download/report").get_json()
    assert result["request_criteria"][0]["outcome"] is None
    assert b"conflicts with the complete window list" in client.get(conflict.location).data
    inspection = client.get(conflict.location + "/download/inspection").get_json()
    assert "CONFLICTING_EVIDENCE" in json.dumps(inspection)


def test_declaration_does_not_fill_line_evidence_or_run_unselected_branch():
    data = MultiDict({"setup_id": "setup-1", "ra": "201.365", "dec": "-43.019",
                      "radius": "30", "sources": "ARCHIVE", "intents": "LINE",
                      "continuum_setup_declaration": "on", "action": "assess"})
    client = create_app(config()).test_client()
    response = client.post("/proposed", data=data)
    doc = client.get(response.location + "/download/report").get_json()
    assert doc["request_criteria"] == []
    assert all(b["status"] == "INDETERMINATE" for c in doc["context_evaluations"] for b in c["branches"])
