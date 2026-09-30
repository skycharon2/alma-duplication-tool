"""Real offline reports, original exports and source/pair presentation."""

import json
from pathlib import Path

import pytest
import requests

from alma_duplicate.cli.acceptance import run_catalog
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.ui import create_app


@pytest.fixture(scope="module")
def reports(tmp_path_factory):
    root = tmp_path_factory.mktemp("ui") / "acceptance"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(requests.sessions.Session, "request",
                      lambda *a, **kw: pytest.fail("unexpected network access"))
        run_catalog(Path(__file__).parents[2] / "examples/acceptance/catalog.json", root)
    return root


def test_catalog_render_export_and_pair_identity(reports, monkeypatch):
    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *a, **kw: pytest.fail("viewer queried a source"))
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": reports}).test_client()
    for index, path in enumerate(sorted(reports.glob("*/report.json")), 1):
        base = f"/reports/{index}"
        raw = path.read_bytes()
        document = json.loads(raw)
        response = client.get(base)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for name, source in document["sources"].items():
            assert f'{name} — {source["status"]}' in html
        for context in document["context_evaluations"][:20]:
            assert context["context_id"] in html
            for branch in context["branches"]:
                assert branch["status"] in html
        downloaded = client.get(base + "/download/report")
        assert downloaded.data == raw
        assert downloaded.headers["Cache-Control"] == "no-store"
        inspection = client.get(base + "/download/inspection").get_json()
        assert inspection == inspect_report(document)
        # Every pair gap still points into this exact downloaded document.
        for gap in inspection["gap_occurrences"]:
            if "pair_identity" in gap:
                node = document
                for token in gap["location"].split("/")[1:]:
                    node = node[int(token)] if isinstance(node, list) else node[token]
                assert "criterion_id" in node
        pages = max(1, (len(document["context_evaluations"]) + 19) // 20)
        for page in range(2, pages + 1):
            assert client.get(base + f"?page={page}").status_code == 200
        assert client.get(base + f"?page={pages+1}").status_code == 404
        assert client.get(base + "/download/report").data == raw


def test_empty_unknown_and_invalid_page():
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": None}).test_client()
    assert b"No reports configured" in client.get("/reports").data
    assert client.get("/reports/../../etc/passwd").status_code == 404
    assert client.get("/reports/1/download/report").status_code == 404


def test_snapshot_escaping_and_page_validation(reports, tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    doc = json.loads((reports / "guide-b/report.json").read_bytes())
    doc["request"]["display_note"] = '<script>alert("x")</script>'
    file = case / "report.json"
    file.write_text(json.dumps(doc))
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": tmp_path}).test_client()
    original = file.read_bytes()
    file.write_text("changed after startup")
    assert client.get("/reports/1/download/report").data == original
    assert b'<script>alert' not in client.get("/reports/1").data
    for value in ("0", "-1", "x", "99999999999"):
        assert client.get("/reports/1?page=" + value).status_code == 400
    assert client.get("/reports/1/download/other").status_code == 404


@pytest.mark.parametrize("raw", [b'{}', b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'])
def test_invalid_reports_fail_startup(tmp_path, raw):
    case = tmp_path / "bad"
    case.mkdir()
    (case / "report.json").write_bytes(raw)
    with pytest.raises(ValueError, match="Invalid UI report"):
        create_app({"REPORT_DIRECTORY": tmp_path})


def test_solar_report_remains_no_search(tmp_path):
    from alma_duplicate.assessment import assess_observation
    from alma_duplicate.reporting import report_json_text

    request = json.loads((Path(__file__).parents[2] / "examples/single_point/request.json").read_text())
    request["request"]["target_kind"] = "SUN"
    result = assess_observation(request["request"], request["search_options"])
    assert result.document is not None
    case = tmp_path / "solar"
    case.mkdir()
    raw = report_json_text(result.document).encode()
    (case / "report.json").write_bytes(raw)
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": tmp_path}).test_client()
    assert b"Solar exemption: search not performed" in client.get("/reports/1").data
    assert client.get("/reports/1/download/report").data == raw
