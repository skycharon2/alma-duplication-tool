"""Explicit live AQ browser execution, immutable exports and report-only display."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from alma_duplicate.assessment import ArchiveInput, AssessmentSources, assess_observation
from alma_duplicate.clients import archive_aq_client, archive_client
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient as RealAqClient, ArchiveAqError
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui import create_app
from alma_duplicate.ui.runs import BrowserAssessment
from tests.integration.test_assessment_entry import normalized
from tests.integration.test_live_aq_assessment import tap_rows
from tests.ui.test_live_source import line_form, live_config
from tests.unit.test_archive_aq_client import BASE, Http, Reply, hit, response


def config(**overrides):
    return live_config(LIVE_AQ=True) | overrides


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("external HTTP"))


@pytest.fixture
def wired(monkeypatch):
    source, _ = tap_rows()
    state = {"source": source, "events": [], "mode": "success", "label": "7m"}

    class Tap:
        def __init__(self, endpoint):
            state["events"].append("TAP_INIT")

        def search(self, query):
            state["events"].append("TAP_SEARCH")
            if isinstance(state["source"], Exception):
                raise state["source"]
            return state["source"]

    class Aq:
        def __init__(self):
            assert state["events"][-1] == "TAP_SEARCH"
            state["events"].append("AQ_INIT")

        def fetch_members(self, members):
            state["events"].append(("AQ_FETCH", members))
            if state["mode"] in {"FAILED", "INCOMPLETE"}:
                raise ArchiveAqError("HTTP_ERROR" if state["mode"] == "FAILED" else "INCOMPLETE", members[0])
            if state["mode"] == "broken":
                raise ValueError("invalid provider contract")
            data = []
            for member in members:
                names = list(dict.fromkeys(r["target_name"] for r in state["source"].rows
                                           if r["member_ous_uid"] == member))
                records = [] if state["mode"] == "empty" else [hit(member, name, state["label"]) for name in names]
                data.append(Reply(response(records)))
            return RealAqClient(request=Http(Reply({"elasticsearchUrl": BASE}), *data)).fetch_members(members)

    monkeypatch.setattr(archive_client, "ArchiveClient", Tap)
    monkeypatch.setattr(archive_aq_client, "ArchiveAqClient", Aq)
    return state


@pytest.mark.parametrize("overrides", [
    {"LIVE_ARCHIVE": False},
    {"OFFLINE_ARCHIVE_REPLAY": "unused.json"},
    {"ARCHIVE_ARRAY_EVIDENCE": "unused.json"},
    {"LIVE_AQ": "true"},
])
def test_conflicting_or_untyped_configuration_fails_without_source_access(wired, overrides):
    with pytest.raises(ValueError):
        create_app(config(**overrides))
    assert wired["events"] == []


@pytest.mark.parametrize("value,enabled", [("1", True), ("true", True), ("YES", True), ("on", True),
                                          ("0", False), ("false", False), ("off", False), ("", False)])
def test_env_flag_is_explicit(monkeypatch, wired, value, enabled):
    monkeypatch.setenv("ALMA_UI_LIVE_ARCHIVE_AQ", value)
    cfg = config()
    del cfg["LIVE_AQ"]
    client = create_app(cfg).test_client()
    html = client.get("/proposed").get_data(as_text=True)
    assert ("Additional AQ evidence: live AQ enabled" in html) is enabled
    assert wired["events"] == []


def test_invalid_environment_flag_is_rejected(monkeypatch, wired):
    monkeypatch.setenv("ALMA_UI_LIVE_ARCHIVE_AQ", "sometimes")
    with pytest.raises(ValueError, match="ALMA_UI_LIVE_ARCHIVE_AQ"):
        create_app(config())
    assert wired["events"] == []


def test_constructor_validate_download_and_unsupported_requests_are_lazy(wired):
    client = create_app(config()).test_client()
    assert client.get("/proposed").status_code == 200
    assert client.get("/healthz").status_code == 200
    for action in ("validate", "download", "purpose", "scope", "add"):
        assert client.post("/proposed", data=line_form(action)).status_code == 200
    for field, value in [("ra", "invalid"), ("target_kind", "SUN"), ("target_kind", "MOVING"), ("geometry", "MOSAIC")]:
        data = line_form()
        data[field] = value
        assert client.post("/proposed", data=data).status_code == 200
    data = line_form()
    data.setlist("sources", ["QUEUE"])
    assert client.post("/proposed", data=data).status_code == 303
    assert wired["events"] == []


@pytest.mark.parametrize("kind,reason", [("empty", "NO_RETAINED_ARCHIVE_CONTEXTS"),
    ("unlinked", "NO_LINKED_ARCHIVE_MEMBERS"), ("failed", "TAP_NOT_COMPLETED"), ("incomplete", "TAP_NOT_COMPLETED")])
def test_aq_client_is_not_created_when_backend_skips(wired, kind, reason):
    source, _ = tap_rows(empty=kind == "empty", unlinked=kind == "unlinked")
    if kind == "failed":
        source = OSError("TAP unavailable")
    if kind == "incomplete":
        source = replace(source, status=ArchiveQueryStatus.OVERFLOW)
    wired["source"] = source
    client = create_app(config()).test_client()
    posted = client.post("/proposed", data=line_form())
    assert posted.status_code == 303
    assert wired["events"] == ["TAP_INIT", "TAP_SEARCH"]
    html = client.get(posted.location).get_data(as_text=True)
    assert "AQ acquisition: SKIPPED" in html and reason in html


def test_live_tap_without_aq_preserves_existing_behavior(wired):
    client = create_app(live_config()).test_client()  # AQ flag absent, environment isolated.
    assert b"Additional AQ evidence: not configured" in client.get("/proposed").data
    posted = client.post("/proposed", data=line_form())
    assert posted.status_code == 303
    assert wired["events"] == ["TAP_INIT", "TAP_SEARCH"]
    doc = client.get(posted.location + "/download/report").get_json()
    assert "array_evidence" not in doc["sources"]["ARCHIVE"]


@pytest.mark.parametrize("mode,status,text", [
    ("success", "COMPLETED", "AQ retrieval completed"),
    ("empty", "COMPLETED", "No source records were returned"),
    ("FAILED", "FAILED", "Live AQ acquisition failed"),
    ("INCOMPLETE", "INCOMPLETE", "No partial catalog was used"),
])
def test_results_keep_candidates_report_and_original_exports(wired, mode, status, text):
    wired["mode"] = mode
    client = create_app(config()).test_client()
    post = client.post("/proposed", data=line_form())
    assert post.status_code == 303
    assert wired["events"][:3] == ["TAP_INIT", "TAP_SEARCH", "AQ_INIT"]
    assert len(wired["events"]) == 4
    location = post.location
    raw = client.get(location + "/download/report").data
    document = json.loads(raw)
    html = client.get(location).get_data(as_text=True)
    assert text in html and f"AQ acquisition: {status}" in html
    assert "Archive TAP status: COMPLETED" in html
    assert "No report was created" not in html
    assert len(document["context_evaluations"]) == 3
    metadata = document["sources"]["ARCHIVE"]["array_evidence"]["acquisition"]
    assert metadata["status"] == status
    if mode in {"FAILED", "INCOMPLETE"}:
        assert document["assessment_status"] == "SOURCES_UNAVAILABLE"
        assert "Planned Members: 2" in html
        assert "No completed query records are available" in html
    else:
        assert "Completed AQ query records, including zero-hit results" in html
        for query in metadata["queries"]:
            assert query["response_sha256"] in html
    inspection = client.get(location + "/download/inspection").data
    request = client.get(location + "/download/request").data
    assert json.loads(inspection) == inspect_report(document)
    assert json.loads(request)["request"]["intents"] == ["LINE"]
    for _ in range(2):
        assert client.get(location + "?page=1").status_code == 200
        for kind, expected in [("report", raw), ("inspection", inspection), ("request", request)]:
            assert client.get(location + "/download/" + kind).data == expected
    assert len(wired["events"]) == 4


def test_contract_exception_is_the_no_report_path(wired):
    wired["mode"] = "broken"
    client = create_app(config()).test_client()
    post = client.post("/proposed", data=line_form())
    assert post.status_code == 200
    assert b"No report was created" in post.data


def test_runs_have_separate_catalogs_and_refresh_does_not_query(wired):
    client = create_app(config()).test_client()
    first = client.post("/proposed", data=line_form()).location
    original = client.get(first + "/download/report").data
    wired["label"] = "12m"
    second = client.post("/proposed", data=line_form()).location
    later = client.get(second + "/download/report").get_json()
    assert first != second
    assert client.get(first + "/download/report").data == original
    assert json.loads(original)["context_evaluations"][0]["array_evidence"]["diameters_m"] == [7.0]
    assert later["context_evaluations"][0]["array_evidence"]["diameters_m"] == [12.0]
    assert len(wired["events"]) == 8


def test_browser_and_shared_entry_have_same_science_and_provenance(monkeypatch, wired):
    from alma_duplicate import archive_array_acquisition
    class Clock:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(archive_array_acquisition, "datetime", Clock)
    monkeypatch.setattr(archive_aq_client, "datetime", Clock)
    client = create_app(config()).test_client()
    location = client.post("/proposed", data=line_form()).location
    document = client.get(location + "/download/report").get_json()
    request = client.get(location + "/download/request").get_json()
    direct = assess_observation(**request, sources=AssessmentSources(
        "LIVE", lambda: ArchiveInput(archive_client.ArchiveClient("https://almascience.eso.org/tap")),
        archive_array_fetcher=lambda members: archive_aq_client.ArchiveAqClient().fetch_members(members)))
    assert normalized(document) == normalized(direct.document)
    assert inspect_report(document) == inspect_report(direct.document)


def test_report_display_uses_saved_provenance_not_operator_config(wired, tmp_path):
    client = create_app(config()).test_client()
    location = client.post("/proposed", data=line_form()).location
    live_doc = client.get(location + "/download/report").get_json()
    old_doc = deepcopy(live_doc)
    del old_doc["sources"]["ARCHIVE"]["array_evidence"]
    old_doc.pop("assessment_status")
    captured_doc = deepcopy(live_doc)
    captured_doc["sources"]["ARCHIVE"]["array_evidence"] = {
        "scope": "CAPTURED_OFFICIAL_AQ_SOURCE_LABELS", "record_count": 1,
        "manifest_sha256": "stored-capture-hash", "method_version": "archive_source_array_1"}
    for name, doc in [("a-live", live_doc), ("b-old", old_doc), ("c-captured", captured_doc)]:
        case = tmp_path / name
        case.mkdir()
        (case / "report.json").write_text(report_json_text(doc))
    events = list(wired["events"])
    for live in (False, True):
        viewer = create_app(config(REPORT_DIRECTORY=tmp_path, LIVE_ARCHIVE=live, LIVE_AQ=live)).test_client()
        assert "Evidence provenance: LIVE" in viewer.get("/reports/1").get_data(as_text=True)
        old = viewer.get("/reports/2").get_data(as_text=True)
        assert "Additional AQ evidence: not recorded in this report" in old
        assert "AQ acquisition:" not in old
        captured = viewer.get("/reports/3").get_data(as_text=True)
        assert "Evidence provenance: CAPTURED" in captured
        assert "AQ acquisition status is not recorded" in captured
        assert viewer.get("/reports/1/download/report").data == report_json_text(live_doc).encode()
    assert wired["events"] == events


def test_pagination_and_external_text_are_safe_without_acquisition(wired, tmp_path):
    source = wired["source"]
    template = source.rows[0]
    member = template["member_ous_uid"]
    rows = tuple(dict(template, target_name=f"Src{i:04d}",
                      obs_id=f"{member}.source.Src{i:04d}.spw.0") for i in range(21))
    wired["source"] = replace(source, rows=rows, provenance=replace(source.provenance,
                              expected_count=21, retrieved_count=21))
    client = create_app(config()).test_client()
    location = client.post("/proposed", data=line_form()).location
    doc = client.get(location + "/download/report").get_json()
    assert len(doc["context_evaluations"]) == 21
    aq = doc["sources"]["ARCHIVE"]["array_evidence"]["acquisition"]
    aq["queries"][0]["member_ous_uid"] = '<script>alert("source")</script>'
    aq["requested_members"][0] = '<script>alert("source")</script>'
    aq["status"] = "FAILED"
    aq["error"] = {"code": '<script>alert("error")</script>', "member_ous_uid": None}
    case = tmp_path / "case"
    case.mkdir()
    raw = report_json_text(doc).encode()
    (case / "report.json").write_bytes(raw)
    events = list(wired["events"])
    viewer = create_app(config(REPORT_DIRECTORY=tmp_path)).test_client()
    for page in (1, 2):
        response_ = viewer.get(f"/reports/1?page={page}")
        assert response_.status_code == 200
        html = response_.get_data(as_text=True)
        assert "<script>" not in html and "&lt;script&gt;" in html
    assert viewer.get("/reports/1/download/report").data == raw
    assert wired["events"] == events


def test_live_aq_boolean_guard_on_direct_browser_configuration():
    with pytest.raises(ValueError, match="boolean"):
        BrowserAssessment(live_archive=True, live_aq=1)


@pytest.mark.parametrize("live,replay,captured", [
    (True, None, None), (True, None, "captured.json"),
    (False, "replay.json", None), (False, "replay.json", "captured.json"),
])
def test_existing_configuration_matrix_is_preserved_without_startup_io(wired, live, replay, captured):
    client = create_app(config(LIVE_AQ=False, LIVE_ARCHIVE=live,
                              OFFLINE_ARCHIVE_REPLAY=replay, ARCHIVE_ARRAY_EVIDENCE=captured)).test_client()
    html = client.get("/proposed").get_data(as_text=True)
    assert ("captured AQ manifest configured" in html) is bool(captured)
    assert wired["events"] == []
