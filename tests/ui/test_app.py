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


def test_index_is_minimal_until_visual_shell_is_added():
    app = create_app({"TESTING": True})
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "ALMA Duplication Assessment\n"
