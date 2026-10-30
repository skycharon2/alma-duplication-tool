"""Default browser-contract guardrails for the first Single Pointing recovery step.

No source is queried here: the tests exercise the actual Flask form roundtrip,
validation and JSON export, not the remote Archive or Queue.
"""

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.ui import create_app


@pytest.fixture
def client():
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None}).test_client()


def continuum_form():
    return MultiDict([
        ("setup_id", "setup-1"),
        ("target_kind", "FIXED"), ("geometry", "SINGLE_POINTING"),
        ("ra", "278.416333333"), ("dec", "-21.061083333"),
        ("ra_format", "DEG"), ("dec_format", "DEG"),
        ("intents", "CONTINUUM"), ("angular", "0.23"),
        ("representative", "290.420"), ("representative_kind", "SKY"),
        ("aggregate", "0.01"), ("continuum_setup_declaration", "on"),
        ("sources", "ARCHIVE"), ("sources", "QUEUE"),
        ("radius_mode", "AUTO"),
    ])


def test_default_is_v2_but_explicit_legacy_submission_is_preserved(client):
    initial = client.get("/proposed").get_data(as_text=True)
    assert 'name="normal_form_version" value="2"' in initial
    assert 'name="normal_line_records"' not in initial

    data = continuum_form()
    data["action"] = "purpose"
    changed = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="normal_line_records"' not in changed
    assert 'id="shared-redshift"' in changed

    data["action"] = "validate"
    validated = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'Input valid: <strong>Yes</strong>' in validated
    assert 'Separated input must not include legacy' not in validated

    data["action"] = "download"
    response = client.post("/proposed", data=data)
    assert response.is_json
    exported = response.get_json()
    request = exported["request"]
    assert "line_input_contract" not in request
    assert request["intents"] == ["CONTINUUM"]
    assert request["sensitivities"][0]["rms"] == {
        "value": "0.01", "unit": "mJy/beam",
    }
    assert exported["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]


def test_new_single_pointing_line_does_not_implicitly_use_v2(client):
    data = continuum_form()
    data.setlist("intents", ["LINE"])
    for key in ("representative", "aggregate", "continuum_setup_declaration"):
        data.pop(key, None)
    row = "w123456abcdef"
    data["rows"] = row
    data[row + "_id"] = "line-0"
    data[row + "_center"] = "230.538"
    data[row + "_center_kind"] = "SKY"
    data[row + "_mode"] = "FDM"
    data[row + "_resolution"] = "20"
    data[row + "_rms"] = "0.3"
    data["action"] = "download"
    response = client.post("/proposed", data=data)
    assert response.is_json
    request = response.get_json()["request"]
    assert "line_input_contract" not in request
    assert request["spectral_windows"][0]["window_id"] == "line-0"


def test_clean_mosaic_scope_keeps_separated_editor(client):
    # A fresh Mosaic selection may opt into the established Mosaic V2 editor.
    data = MultiDict([
        ("setup_id", "setup-1"), ("target_kind", "FIXED"),
        ("geometry", "MOSAIC"), ("sources", "ARCHIVE"),
        ("action", "scope"),
    ])
    scope = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="normal_form_version" value="2"' in scope

    data["normal_form_version"] = "2"
    data["intents"] = "CONTINUUM"
    data["action"] = "purpose"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="normal_line_records" value="1"' in html
    assert 'Physical SPW evidence' in html
    assert 'name="frequency_local_redshift"' in html


def test_populated_legacy_request_is_not_auto_upgraded_when_switching_to_mosaic(client):
    # A geometry change must not reinterpret already supplied Legacy science data.
    data = continuum_form()
    data["geometry"] = "MOSAIC"
    data["action"] = "scope"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="normal_form_version"' not in html
    assert 'name="normal_line_records"' not in html


def test_explicit_v2_with_queue_does_not_silently_downgrade(client):
    data = continuum_form()
    data["normal_form_version"] = "2"
    data["action"] = "purpose"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="normal_line_records" value="1"' in html

    data["normal_line_records"] = "1"
    data["action"] = "download"
    response = client.post("/proposed", data=data)
    assert response.is_json
    exported = response.get_json()
    assert exported['request']['line_input_contract'] == 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'
    assert exported['search_options']['sources'] == ['ARCHIVE', 'QUEUE']
