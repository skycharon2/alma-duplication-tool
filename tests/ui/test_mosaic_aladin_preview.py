"""Proposed Mosaic sky context must remain optional and never alter science."""
from alma_duplicate.ui import create_app


def test_mosaic_sky_has_aladin_and_geometry_fallback():
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    response = app.test_client().get('/proposed/mosaic')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="mosaic-aladin"' in html
    assert 'data-mosaic-canvas' in html
    assert 'data-mosaic-map-stack' in html
    assert '/static/alma-sky-runtime.js' in html
    assert '/static/mosaic-aladin.js' in html
    assert '/static/vendor/aladin-lite/3.8.2/aladin.js' in html
    app.extensions['assessment_runs'].close()


def test_single_pointing_does_not_gain_mosaic_controls():
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None})
    html = app.test_client().get('/proposed').get_data(as_text=True)
    assert 'id="mosaic-aladin"' not in html
    assert 'data-mosaic-map-stack' not in html
    app.extensions['assessment_runs'].close()
