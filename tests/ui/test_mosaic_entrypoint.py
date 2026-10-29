"""PR 3B-1: opt-in Mosaic route, retained legacy entry and no source I/O."""

import io
import re

import pytest

from alma_duplicate.ui import create_app
from alma_duplicate.ui.workflow_policy import initial_mosaic_values
from tests.ui.test_default_single_pointing_contract import continuum_form
from tests.ui.test_mosaic_ot_preview import OT


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    yield app.test_client()
    app.extensions["assessment_runs"].close()


def test_isolated_mosaic_initial_state_does_not_mutate_single():
    original = {"setup_id": "setup-1", "sources": ["ARCHIVE", "QUEUE"]}
    mosaic = initial_mosaic_values(original)
    assert original["sources"] == ["ARCHIVE", "QUEUE"]
    assert "normal_form_version" not in original
    assert mosaic["sources"] == ["ARCHIVE"]
    assert mosaic["normal_form_version"] == "2"
    assert mosaic["geometry"] == "MOSAIC"
    assert mosaic["target_kind"] == "FIXED"


def test_two_get_entrypoints_have_distinct_default_scope(client):
    single = client.get("/proposed")
    mosaic = client.get("/proposed/mosaic")
    assert single.status_code == mosaic.status_code == 200
    assert 'action="/proposed"' in single.text
    assert 'action="/proposed/mosaic"' in mosaic.text
    assert 'name="normal_form_version"' not in single.text
    assert 'name="normal_form_version" value="2"' in mosaic.text
    assert 'name="sources" value="ARCHIVE"' in mosaic.text
    assert 'name="sources" value="QUEUE"' not in mosaic.text
    assert 'name="target_kind" value="FIXED"' in mosaic.text
    assert 'name="geometry" value="MOSAIC"' in mosaic.text
    assert 'select id="geometry"' not in mosaic.text
    assert 'id="mosaic-pointings"' in mosaic.text
    assert 'href="/proposed/mosaic"' in single.text
    assert 'href="/proposed"' in mosaic.text


def test_standard_single_export_keeps_both_sources(client):
    data = continuum_form()
    data["action"] = "download"
    response = client.post("/proposed", data=data)
    assert response.is_json
    exported = response.get_json()
    assert exported["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
    assert "line_input_contract" not in exported["request"]


@pytest.mark.parametrize("scope", [
    {"target_kind": "FIXED", "geometry": "SINGLE_POINTING"},
    {"target_kind": "MOVING", "geometry": "MOSAIC"},
    {"target_kind": "SUN", "geometry": "MOSAIC"},
    {"target_kind": "FIXED"},
])
def test_mosaic_entry_rejects_forged_non_mosaic_post(client, scope):
    response = client.post("/proposed/mosaic", data=scope | {"action": "scope"})
    assert response.status_code == 400


def test_new_mosaic_route_enforces_archive_only_on_post(client):
    result = client.post("/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC",
        "normal_form_version": "2", "sources": ["ARCHIVE", "QUEUE"],
        "action": "scope",
    })
    assert result.status_code == 200
    assert 'action="/proposed/mosaic"' in result.text
    assert 'name="sources" value="ARCHIVE"' in result.text
    assert 'name="sources" value="QUEUE"' not in result.text


def test_new_mosaic_route_keeps_post_action_and_v2(client):
    data = {"target_kind": "FIXED", "geometry": "MOSAIC",
            "setup_id": "setup-1", "normal_form_version": "2",
            "sources": "ARCHIVE", "intents": "CONTINUUM", "action": "purpose"}
    result = client.post("/proposed/mosaic", data=data)
    assert result.status_code == 200
    assert 'action="/proposed/mosaic"' in result.text
    assert 'name="normal_line_records" value="1"' in result.text
    assert 'id="mosaic-pointings"' in result.text


def test_new_mosaic_route_preserves_ot_upload_token(client):
    first = client.post("/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC",
        "mosaic_array": "12m", "normal_form_version": "2",
        "sources": "ARCHIVE", "action": "preview-pointings",
        "ot_pointings": (io.BytesIO(OT), "pointings.txt"),
    }, content_type="multipart/form-data")
    assert first.status_code == 200
    assert 'id="mosaic-preview-result"' in first.text
    match = re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', first.text)
    assert match is not None
    second = client.post("/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC",
        "mosaic_upload_token": match.group(1),
        "normal_form_version": "2", "action": "scope", "sources": "ARCHIVE",
    })
    assert second.status_code == 200
    assert 'action="/proposed/mosaic"' in second.text
    assert 'id="mosaic-preview-result"' in second.text


def test_old_mosaic_post_remains_compatible_during_migration(client):
    response = client.post("/proposed", data={
        "target_kind": "FIXED", "geometry": "MOSAIC",
        "setup_id": "setup-1", "sources": "ARCHIVE", "action": "scope",
    })
    assert response.status_code == 200
    assert 'action="/proposed"' in response.text
    assert 'id="mosaic-pointings"' in response.text
