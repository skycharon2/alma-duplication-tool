"""PR 3B-5: separate POST controllers, preserve old routes and science inputs."""

import io
import re

import pytest

from alma_duplicate.ui import create_app
from tests.ui.test_default_single_pointing_contract import continuum_form
from tests.ui.test_mosaic_ot_preview import OT


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    yield app.test_client()
    app.extensions["assessment_runs"].close()


def test_single_post_download_preserves_archive_and_queue(client):
    data = continuum_form()
    data["action"] = "download"
    response = client.post("/proposed", data=data)
    assert response.status_code == 200
    assert response.get_json()["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
    assert "line_input_contract" not in response.get_json()["request"]


def test_mosaic_post_keeps_archive_only_and_v2(client):
    response = client.post("/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "normal_form_version": "2",
        "sources": ["ARCHIVE", "QUEUE"], "action": "scope", "setup_id": "setup-1",
    })
    assert response.status_code == 200
    assert 'action="/proposed/mosaic"' in response.text
    assert 'name="sources" value="QUEUE"' not in response.text
    assert 'name="normal_form_version" value="2"' in response.text


@pytest.mark.parametrize("target,geometry", [
    ("FIXED", "SINGLE_POINTING"), ("MOVING", "MOSAIC"), ("SUN", "MOSAIC"),
])
def test_dedicated_mosaic_rejects_non_mosaic_posts(client, target, geometry):
    response = client.post("/proposed/mosaic", data={
        "target_kind": target, "geometry": geometry, "action": "scope",
    })
    assert response.status_code == 400


def test_old_mosaic_post_stays_on_single_url_and_uploads(client):
    response = client.post("/proposed", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "sources": "ARCHIVE",
        "action": "preview-pointings", "mosaic_array": "12m",
        "ot_pointings": (io.BytesIO(OT), "pointings.txt"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    assert 'action="/proposed"' in response.text
    assert 'data-workflow="single"' in response.text
    assert 'id="mosaic-preview-result"' in response.text
    match = re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', response.text)
    assert match is not None
    removed = client.post("/proposed", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "action": "remove-pointings",
        "mosaic_upload_token": match.group(1), "sources": "ARCHIVE",
    })
    assert removed.status_code == 200
    assert 'id="mosaic-preview-result"' not in removed.text
    assert 'action="/proposed"' in removed.text


def test_single_cannot_post_mosaic_upload_action(client):
    response = client.post("/proposed", data={
        "target_kind": "FIXED", "geometry": "SINGLE_POINTING",
        "action": "preview-pointings",
    })
    assert response.status_code == 400


def test_independent_validation_does_not_query_sources(client, monkeypatch):
    from alma_duplicate.ui import runs

    def forbidden(*args, **kwargs):
        raise AssertionError("Validation must not execute either science workflow")

    monkeypatch.setattr(runs.BrowserAssessment, "assess", forbidden)
    monkeypatch.setattr(runs.BrowserAssessment, "assess_mosaic", forbidden)
    data = continuum_form()
    data["action"] = "validate"
    single = client.post("/proposed", data=data)
    mosaic = client.post("/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "sources": "ARCHIVE",
        "action": "validate", "setup_id": "setup-1",
    })
    assert single.status_code == mosaic.status_code == 200
    assert 'action="/proposed"' in single.text
    assert 'action="/proposed/mosaic"' in mosaic.text


def test_single_assess_dispatch_never_calls_mosaic(monkeypatch):
    from alma_duplicate.ui.runs import BrowserAssessment
    from tests.ui.test_runs import config, line_form

    calls = []

    def selected(self, document):
        calls.append("single")
        raise ValueError("injected Single Pointing source failure")

    def forbidden(*args, **kwargs):
        pytest.fail("Mosaic runner reached from Single Pointing")

    monkeypatch.setattr(BrowserAssessment, "assess", selected)
    monkeypatch.setattr(BrowserAssessment, "assess_mosaic", forbidden)
    app = create_app(config())
    try:
        response = app.test_client().post("/proposed", data=line_form())
        assert response.status_code == 200
        assert "Assessment could not be completed" in response.text
        assert calls == ["single"]
    finally:
        app.extensions["assessment_runs"].close()


def test_mosaic_assess_dispatch_never_calls_single(monkeypatch):
    import json
    from alma_duplicate.ui.runs import BrowserAssessment
    from tests.ui.test_mosaic_execution import ROOT, form

    calls = []

    def selected(self, document, points):
        calls.append("mosaic")
        assert points is not None
        raise ValueError("injected Mosaic source failure")

    def forbidden(*args, **kwargs):
        pytest.fail("Single Pointing runner reached from Mosaic")

    monkeypatch.setattr(BrowserAssessment, "assess_mosaic", selected)
    monkeypatch.setattr(BrowserAssessment, "assess", forbidden)
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None, "LIVE_ARCHIVE": True})
    try:
        client = app.test_client()
        raw = json.loads((ROOT / "proposed.json").read_text())["raw_text"].encode()
        uploaded = client.post("/proposed/mosaic", data=form() | {
            "action": "preview-pointings", "ot_pointings": (io.BytesIO(raw), "pointings.txt"),
        }, content_type="multipart/form-data")
        assert uploaded.status_code == 200
        match = re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', uploaded.text)
        assert match is not None
        response = client.post("/proposed/mosaic", data=form() | {
            "action": "assess", "mosaic_upload_token": match.group(1),
        })
        assert response.status_code == 200
        assert "Assessment could not be completed" in response.text
        assert calls == ["mosaic"]
    finally:
        app.extensions["assessment_runs"].close()
