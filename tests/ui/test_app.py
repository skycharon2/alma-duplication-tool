"""Thin UI application skeleton tests."""

from alma_duplicate.ui import create_app


def test_app_factory_accepts_test_configuration():
    app = create_app({"TESTING": True})
    assert app.testing is True


def test_health_endpoint_is_side_effect_free():
    app = create_app({"TESTING": True})
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_opens_working_observation_form():
    app = create_app({"TESTING": True})
    response = app.test_client().get("/")
    assert response.status_code == 302
    assert response.location == "/proposed"
    response = app.test_client().get(response.location)
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert "ALMA Duplication Assessment" in html
    assert "Visual preview" not in html
    assert 'action="/proposed"' in html
    assert "No assessment has been run" in html
