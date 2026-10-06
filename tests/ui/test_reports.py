"""Real offline reports, original exports and source/pair presentation."""

import json
from html.parser import HTMLParser
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
        response = client.get(base + "?view=all")
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
            assert client.get(base + f"?page={page}&view=all").status_code == 200
        assert client.get(base + f"?page={pages+1}&view=all").status_code == 404
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
    html = client.get("/reports/1?view=all").get_data(as_text=True)
    parser = Tables()
    parser.feed(html)
    candidate_table = parser.tables[0]
    assert "CONTINUUM" not in candidate_table  # Friendly column heading, no synthesized branch.
    assert "Continuum" not in candidate_table and "Spectral line" in candidate_table
    assert "Meets these conditions" in candidate_table
    assert "CRITERIA_MET" not in candidate_table
    pair_tables = [t for t in parser.tables if "Criteria for this LINE pair" in t]
    pairs = [p for c in doc["context_evaluations"] for p in c["line_pairs"]]
    assert len(pair_tables) == len(pairs)
    for table, pair in zip(pair_tables, pairs):
        for result in pair["criteria"]:
            from alma_duplicate.ui.report_view import criterion_view, criterion_status
            assert criterion_view(result)["label"] in table
            assert criterion_status(result) in table
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


def test_archive_mixed_beam_report_preserves_source_evidence_and_downloads(tmp_path):
    from alma_duplicate.reporting import report_document, report_json_text
    from alma_duplicate.rules.evaluation import evaluate_candidate_search
    from tests.integration.test_archive_array_adapter import synthetic

    search, catalog = synthetic(intents=("CONTINUUM", "LINE"))
    doc = report_document(evaluate_candidate_search(search, archive_arrays=catalog))
    raw = report_json_text(doc).encode()
    case = tmp_path / "archive-mixed"
    case.mkdir()
    (case / "report.json").write_bytes(raw)
    client = create_app({"TESTING": True, "REPORT_DIRECTORY": tmp_path}).test_client()
    response = client.get("/reports/1")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Archive beam hypotheses: 7 m + 12 m" in html
    assert "synthetic-manifest" in html
    assert html.count('id="context-0"') == 1
    assert 'id="pair-0-beam-0-0"' in html and 'id="pair-0-beam-1-0"' in html
    assert client.get("/reports/1/download/report").data == raw
    assert client.get("/reports/1/download/inspection").get_json() == inspect_report(doc)


class DefaultVisibleText(HTMLParser):
    """Text visible before opening native details; no CSS hiding assumptions."""
    def __init__(self):
        super().__init__()
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, tag == 'details' and 'open' not in dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for i, (_, closed) in enumerate(self.stack):
            if closed and (i + 1 == len(self.stack) or self.stack[i + 1][0] != 'summary'):
                return
        self.text.append(data)


def test_default_view_has_no_raw_records_and_keeps_source_failures_visible(reports, tmp_path):
    doc = json.loads((reports / 'missing-line-rms/report.json').read_bytes())
    doc['sources']['ARCHIVE']['array_evidence'] = {
        'scope': 'LIVE_OFFICIAL_AQ_SOURCE_LABELS', 'record_count': 0,
        'acquisition': {'status': 'FAILED', 'requested_members': [], 'queries': [],
                        'error': {'code': 'TEST_FAILURE', 'member_ous_uid': None}}}
    case = tmp_path / 'failure'
    case.mkdir()
    raw = json.dumps(doc).encode()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    html = client.get('/reports/1').get_data(as_text=True)
    parser = DefaultVisibleText()
    parser.feed(html)
    visible = ' '.join(parser.text)
    for code in ['CRITERIA_MET', 'CRITERIA_NOT_MET', 'NOT_AGGREGATED', 'PLANNED_LINE_RMS_REQUIRED',
                 'TEST_FAILURE', '"context_evaluations"', 'archive_line_context_or_1']:
        assert code not in visible
        if code in json.dumps(doc):
            assert code in client.get('/reports/1?view=all').get_data(as_text=True)  # Full audit view.
    assert 'Array evidence retrieval failed' in visible
    assert 'Enter the planned RMS for this proposed line.' in visible
    assert 'Technical records' in visible
    assert client.get('/reports/1/download/report').data == raw
    assert client.get('/reports/1/download/inspection').get_json() == inspect_report(doc)


def test_solar_does_not_display_zero_candidate_summary(tmp_path):
    from alma_duplicate.assessment import assess_observation
    from alma_duplicate.reporting import report_json_text
    doc = assess_observation({'target_kind': 'SUN', 'geometry': 'SINGLE_POINTING',
                              'setup_id': 'sun', 'intents': ['CONTINUUM']}, {}).document
    case = tmp_path / 'solar'
    case.mkdir()
    (case / 'report.json').write_text(report_json_text(doc))
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    parser = DefaultVisibleText()
    parser.feed(client.get('/reports/1').get_data(as_text=True))
    visible = ' '.join(parser.text)
    assert 'Solar exemption: search not performed' in visible
    assert '0 candidate comparisons evaluated' not in visible


@pytest.mark.parametrize('source_status', ['COMPLETED', 'FAILED', 'INCOMPLETE', 'NOT_PROVIDED'])
def test_empty_results_and_source_failure_never_claim_no_duplication(reports, tmp_path, source_status):
    doc = json.loads((reports / 'guide-b/report.json').read_bytes())
    doc['context_evaluations'] = []
    doc['sources']['ARCHIVE']['status'] = source_status
    case = tmp_path / 'empty'
    case.mkdir()
    raw = json.dumps(doc).encode()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    html = client.get('/reports/1').get_data(as_text=True)
    parser = DefaultVisibleText()
    parser.feed(html)
    visible = ' '.join(parser.text)
    assert 'No evaluated candidates are available for this check.' in visible
    assert 'An empty result does not establish that there is no duplication.' in visible
    assert 'None of the evaluated candidates meet' not in visible
    if source_status != 'COMPLETED':
        assert 'Search or evidence is incomplete.' in visible
    for label in ('Download complete original JSON', 'Download inspection v3'):
        assert label in html
        assert label not in visible
    assert client.get('/reports/1/download/report').data == raw


def test_one_member_keeps_all_matches_on_one_page_and_preserves_full_export(reports, tmp_path):
    doc = json.loads((reports / 'guide-b/report.json').read_bytes())
    original = doc['context_evaluations'][0]
    contexts = []
    for i in range(49):
        context = json.loads(json.dumps(original).replace(original['context_id'], f"{original['context_id']}:row-{i}"))
        for branch in context['branches']:
            branch['status'] = 'CRITERIA_MET' if i % 2 else 'CRITERIA_NOT_MET'
        contexts.append(context)
    doc['context_evaluations'] = contexts
    case = tmp_path / 'filtered'
    case.mkdir()
    raw = json.dumps(doc).encode()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    html = client.get('/reports/1').get_data(as_text=True)
    assert '24 matching comparisons' in html
    assert 'id="context-1"' in html and 'id="context-39"' in html
    assert 'id="context-0"' not in html
    assert 'id="context-41"' in html and 'id="context-47"' in html
    assert '1 result groups' in html
    assert client.get('/reports/1?page=2').status_code == 404
    all_html = client.get('/reports/1?view=all&page=3').get_data(as_text=True)
    assert 'id="context-40"' in all_html and 'id="context-48"' in all_html
    assert client.get('/reports/1?view=unknown').status_code == 400
    assert client.get('/reports/1/download/report').data == raw


def test_unresolved_case_is_not_listed_as_match_but_keeps_actionable_evidence(reports, tmp_path):
    case = tmp_path / 'unresolved'
    case.mkdir()
    raw = (reports / 'missing-line-rms/report.json').read_bytes()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    html = client.get('/reports/1').get_data(as_text=True)
    visible = DefaultVisibleText()
    visible.feed(html)
    text = ' '.join(visible.text)
    assert 'No matching candidates are available' in text
    assert 'Enter the planned RMS for this proposed line.' in text
    assert 'id="context-0"' not in html
    assert 'page=1&amp;view=all#context-0' in html
    assert 'id="context-0"' in client.get('/reports/1?page=1&view=all').get_data(as_text=True)
    assert client.get('/reports/1/download/report').data == raw


def test_member_pages_keep_interleaved_contexts_together_and_escape_identity(reports, tmp_path):
    from copy import deepcopy
    from html import escape
    from alma_duplicate.ui.report_view import context_identity
    doc = json.loads((reports / 'guide-b/report.json').read_bytes())
    original = doc['context_evaluations'][0]
    member = dict(context_identity(original))['Member OUS']
    contexts = []
    for i in range(22):
        # The final context belongs to the first Member, after twenty other Members.
        member_index = i if i < 21 else 0
        new_member = f'uid://Member/{member_index}/<script>'
        context = json.loads(json.dumps(original).replace(member, new_member).replace(
            original['context_id'], original['context_id'] + f':row-{i}'))
        for branch in context['branches']:
            branch['status'] = 'CRITERIA_MET'
        contexts.append(context)
    doc['context_evaluations'] = contexts
    case = tmp_path / 'members'
    case.mkdir()
    raw = json.dumps(doc).encode()
    (case / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    first = client.get('/reports/1').get_data(as_text=True)
    second = client.get('/reports/1?page=2').get_data(as_text=True)
    assert '21 result groups' in first
    assert 'id="context-0"' in first and 'id="context-21"' in first
    assert 'id="context-20"' not in first
    assert 'id="context-20"' in second and 'id="context-21"' not in second
    assert 'page=2&amp;view=matches' in first
    assert 'page=1&amp;view=matches' in second
    assert escape('uid://Member/0/<script>') in first
    assert 'uid://Member/0/<script>' not in first
    assert 'not every observation in this Member OUS' in first
    assert client.get('/reports/1?page=3').status_code == 404
    assert client.get('/reports/1/download/report').data == raw
    assert client.get('/reports/1/download/inspection').get_json() == inspect_report(deepcopy(doc))
