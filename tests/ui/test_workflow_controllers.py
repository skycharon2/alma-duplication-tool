"""Distinct browser controllers and Mosaic preparation without source queries."""

from types import SimpleNamespace

import pytest

from alma_duplicate.ui import create_app
from alma_duplicate.ui import mosaic_form
from tests.ui.test_default_single_pointing_contract import continuum_form


@pytest.fixture
def app():
    application = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    yield application
    application.extensions["assessment_runs"].close()


def test_distinct_flask_entrypoints_preserve_url_contract(app):
    assert app.view_functions["proposed"] is not app.view_functions["proposed_mosaic"]
    routes = {rule.rule: rule.endpoint for rule in app.url_map.iter_rules()}
    assert routes["/proposed"] == "proposed"
    assert routes["/proposed/mosaic"] == "proposed_mosaic"
    with app.test_client() as client:
        single = client.get("/proposed")
        mosaic = client.get("/proposed/mosaic")
        assert single.status_code == mosaic.status_code == 200
        assert 'action="/proposed"' in single.text
        assert 'action="/proposed/mosaic"' in mosaic.text
        assert 'name="sources" value="QUEUE"' in single.text
        assert 'name="sources" value="QUEUE"' not in mosaic.text


def test_single_pointing_dual_source_download_unchanged(app):
    data = continuum_form()
    data["action"] = "download"
    with app.test_client() as client:
        response = client.post("/proposed", data=data)
    assert response.status_code == 200
    assert response.get_json()["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
    assert "line_input_contract" not in response.get_json()["request"]


def test_legacy_mosaic_post_still_renders_its_scope(app):
    with app.test_client() as client:
        response = client.post("/proposed", data={
            "target_kind": "FIXED", "geometry": "MOSAIC", "sources": "ARCHIVE",
            "action": "scope", "setup_id": "setup-1",
        })
    assert response.status_code == 200
    assert 'action="/proposed"' in response.text
    assert 'id="mosaic-pointings"' in response.text


def issue(category, path, code="SAMPLE"):
    return {"field": "test-field", "issue": SimpleNamespace(
        category=category, path=path, code=code)}


def test_mosaic_preparation_keeps_only_applicable_diagnostics(monkeypatch):
    expected_points = {"points": [{"id": "row-1"}]}
    monkeypatch.setattr(mosaic_form, "bind_mosaic_input",
                        lambda values, preview: expected_points)
    diagnostics = [
        issue("MISSING", "request.position"),
        issue("MISSING", "search_options.radius"),
        issue("CAPABILITY", "request", "METHOD_NOT_IMPLEMENTED"),
        issue("MISSING", "request.setup_id"),
        issue("ERROR", "request.position.ra"),
        issue("CAPABILITY", "request", "BROWSER_V2_SCOPE_UNSUPPORTED"),
    ]
    keep, points, ready, error = mosaic_form.prepare_mosaic_validation(
        {"geometry": "MOSAIC"}, None, diagnostics, SimpleNamespace(is_valid=True),
        live_archive=True)
    assert keep == diagnostics[3:]
    assert points is expected_points
    assert ready is True
    assert error is None


@pytest.mark.parametrize("valid,live,ready", [
    (True, False, False), (False, True, False), (False, False, False),
    (True, True, True),
])
def test_mosaic_readiness_requires_valid_input_and_live_archive(
        monkeypatch, valid, live, ready):
    monkeypatch.setattr(mosaic_form, "bind_mosaic_input", lambda *args: {"points": []})
    _, points, actual, error = mosaic_form.prepare_mosaic_validation(
        {}, None, [], SimpleNamespace(is_valid=valid), live_archive=live)
    assert points == {"points": []}
    assert actual is ready
    assert error is None


def test_invalid_mosaic_evidence_preserves_error_and_diagnostics(monkeypatch):
    def invalid(*args):
        raise ValueError("Missing verified OT pointing collection")

    monkeypatch.setattr(mosaic_form, "bind_mosaic_input", invalid)
    diagnostic = issue("ERROR", "request.angular_resolution")
    keep, points, ready, error = mosaic_form.prepare_mosaic_validation(
        {}, None, [diagnostic], SimpleNamespace(is_valid=True), live_archive=True)
    assert keep == [diagnostic]
    assert points is None and ready is False
    assert error == "Missing verified OT pointing collection"
