"""Template selection must not alter workflow/legacy POST semantics."""

import pytest
from flask import template_rendered

from alma_duplicate.ui import create_app


@pytest.fixture
def app():
    application = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    yield application
    application.extensions["assessment_runs"].close()


def request_template(app, method, path, *, data=None):
    names = []

    def receiver(sender, template, context, **kwargs):
        names.append(template.name)

    template_rendered.connect(receiver, app, weak=False)
    try:
        with app.test_client() as client:
            response = client.open(path, method=method, data=data)
    finally:
        template_rendered.disconnect(receiver, app)
    assert response.status_code == 200
    assert len(names) == 1
    return names[0], response.text


def test_get_routes_use_distinct_templates_and_source_defaults(app):
    single_template, single = request_template(app, "GET", "/proposed")
    mosaic_template, mosaic = request_template(app, "GET", "/proposed/mosaic")
    assert single_template == "proposed_single.html"
    assert mosaic_template == "proposed_mosaic.html"
    assert 'action="/proposed"' in single
    assert 'action="/proposed/mosaic"' in mosaic
    assert 'data-workflow="single"' in single
    assert 'data-workflow="mosaic"' in mosaic
    assert 'name="sources" value="ARCHIVE" checked' in single
    assert 'name="sources" value="QUEUE" checked' in single
    assert 'name="sources" value="ARCHIVE" checked' in mosaic
    assert 'name="sources" value="QUEUE"' not in mosaic
    assert 'name="target_kind" value="FIXED"' in mosaic
    assert 'id="geometry" name="geometry"' in single
    assert 'id="geometry" name="geometry"' in mosaic


def test_legacy_mosaic_post_keeps_single_route_and_upload_ui(app):
    template, html = request_template(app, "POST", "/proposed", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "sources": "ARCHIVE",
        "action": "scope", "setup_id": "setup-1",
    })
    assert template == "proposed_single.html"
    assert 'action="/proposed"' in html
    assert 'id="mosaic-pointings"' in html
    assert 'name="sources" value="QUEUE"' not in html


def test_mosaic_post_keeps_dedicated_route(app):
    template, html = request_template(app, "POST", "/proposed/mosaic", data={
        "target_kind": "FIXED", "geometry": "MOSAIC", "sources": "ARCHIVE",
        "action": "scope", "setup_id": "setup-1",
    })
    assert template == "proposed_mosaic.html"
    assert 'action="/proposed/mosaic"' in html
    assert 'id="mosaic-pointings"' in html
    assert 'name="sources" value="QUEUE"' not in html
