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


def test_comparison_projection_preserves_units_nulls_and_pair_binding(reports):
    from copy import deepcopy
    from alma_duplicate.ui.report_view import criterion_view, pair_binding

    document = json.loads((reports / "dual-source-line/report.json").read_bytes())
    original = deepcopy(document)
    contexts = document["context_evaluations"]
    archive = next(c for c in contexts if c["reference"]["source"] == "ARCHIVE")
    queue = next(c for c in contexts if c["reference"]["source"] == "QUEUE")
    archive_pair, queue_pair = archive["line_pairs"][0], queue["line_pairs"][0]
    assert ("spw_token", "0") in pair_binding(archive_pair)
    assert ("spw_index", 0) in pair_binding(archive_pair)
    assert ("spw_number", 1) in pair_binding(queue_pair)
    assert ("source_row_id", queue_pair["attempt"]["reference"]["source_row_id"]) in pair_binding(queue_pair)
    for pair, unit, key in [
        (archive_pair, "mJy/beam", "sigma_comp_mjy_beam"),
        (queue_pair, "mJy", "comparable_queue_rms_mjy"),
    ]:
        rms = next(r for r in pair["criteria"] if r["criterion_id"] == "LINE-RMS")
        view = criterion_view(rms)
        assert view["candidate"]["unit"] == unit
        assert next(x for x in view["derived"] if x["key"] == key)["unit"] == unit
        assert view["record"]["method_version"] == rms["method_version"]
    assert document == original
    coarse = json.loads((reports / "coarse-line-resolution/report.json").read_bytes())
    rms = coarse["context_evaluations"][0]["line_pairs"][0]["criteria"][-1]
    view = criterion_view(rms)
    assert view["record"]["outcome"] is None
    assert "ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED" in view["record"]["reasons"]
    assert next(x for x in view["derived"] if x["key"] == "sigma_comp_mjy_beam")["value"] is None
    unknown = deepcopy(rms)
    unknown["derived"].append(["future_measurement", 0])
    assert criterion_view(unknown)["derived"][-1] == {
        "key": "future_measurement", "label": "future_measurement", "unit": "", "value": 0,
    }


def test_comparison_tables_keep_pairs_separate_and_escape_values(reports, tmp_path):
    from html.parser import HTMLParser

    class Tables(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables = []
            self.current = None

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.current = []
            if tag == "script":
                pytest.fail("unescaped report content")

        def handle_data(self, data):
            if self.current is not None:
                self.current.append(data)

        def handle_endtag(self, tag):
            if tag == "table":
                self.tables.append(" ".join(self.current))
                self.current = None

    doc = json.loads((reports / "dual-source-line/report.json").read_bytes())
    doc["context_evaluations"][0]["line_pairs"][0]["criteria"][-1]["candidate"]["source_field"] = '<script>alert(1)</script>'
    case = tmp_path / "case"
    case.mkdir()
    raw = json.dumps(doc).encode()
    (case / "report.json").write_bytes(raw)
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": tmp_path}).test_client()
    html = client.get("/reports/1").get_data(as_text=True)
    parser = Tables()
    parser.feed(html)
    candidate_table = parser.tables[0]
    assert "CONTINUUM" not in candidate_table  # Friendly column heading, no synthesized branch.
    assert "No branch result" in candidate_table and "CRITERIA_MET" in candidate_table
    pair_tables = [t for t in parser.tables if "Criteria for this LINE pair" in t]
    pairs = [p for c in doc["context_evaluations"] for p in c["line_pairs"]]
    assert len(pair_tables) == len(pairs)
    for table, pair in zip(pair_tables, pairs):
        for result in pair["criteria"]:
            assert result["criterion_id"] in table
            assert (result["outcome"] or "Not computed") in table
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert client.get("/reports/1/download/report").data == raw


def test_mixed_beam_report_renders_both_variants_without_duplicate_candidates(tmp_path):
    from alma_duplicate.reporting import report_document, report_json_text
    from alma_duplicate.rules.evaluation import evaluate_candidate_search
    from tests.integration.test_queue_beam_variants import mixed

    search, _, _ = mixed(intents=('CONTINUUM', 'LINE'))
    doc = report_document(evaluate_candidate_search(search, queue_continuum=True, queue_line=True))
    raw = report_json_text(doc).encode()
    case = tmp_path / 'mixed'
    case.mkdir()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    response = client.get('/reports/1')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Queue beam hypotheses: 7 m + 12 m' in html
    assert 'Beam variant · D = 7.0 m' in html
    assert 'Beam variant · D = 12.0 m' in html
    assert 'Matching beam diameters (m): 7.0.' in html
    assert html.count('id="context-0"') == 1
    assert 'id="context-1"' not in html
    assert 'id="pair-0-beam-0-0"' in html
    assert 'id="pair-0-beam-1-0"' in html
    assert client.get('/reports/1/download/report').data == raw
    assert client.get('/reports/1/download/inspection').get_json() == inspect_report(doc)
