"""Wire mapping and shared-validator parity without assessment or source access."""

import re

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.reporting import json_value
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.ui import create_app
from alma_duplicate.ui.proposed import build_document, validate_form

ROW = "w123456abcdef"
OTHER = "wabcdef123456"


def fields():
    return {"rows": ROW, "setup_id": "setup-1", "setup_complete": "on",
            "ra": "201.365", "dec": "-43.019", "radius": "30",
            "sources": "ARCHIVE", "intents": "LINE", "angular": "0.3",
            "redshift": "0.024", ROW + "_id": "line-0",
            ROW + "_center": "230.538", ROW + "_center_kind": "REST",
            ROW + "_mode": "FDM", ROW + "_resolution": "20",
            ROW + "_rms": "0.3", "action": "validate"}


@pytest.fixture
def client(monkeypatch):
    import alma_duplicate.assessment as application
    import requests
    monkeypatch.setattr(application, "assess_observation", lambda *a, **k: pytest.fail("assessment invoked"))
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network invoked"))
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None}).test_client()


def test_initial_and_line_validation(client):
    assert client.get("/proposed").status_code == 200
    response = client.post("/proposed", data=fields())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Input valid: <strong>Yes</strong>' in html
    assert 'Search readiness: <strong>READY</strong>' in html
    assert 'value="230.538"' in html
    assert 'REST_FREQUENCY_RETAINED' in html


def test_continuum_confirmation_is_explicit_preserved_and_removable(client):
    data = {"setup_id": "setup-1", "ra": "201.365", "dec": "-43.019",
            "radius": "30", "sources": "ARCHIVE", "intents": "CONTINUUM",
            "continuum_setup_declaration": "on", "action": "validate"}
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="continuum_setup_declaration" aria-describedby="continuum_setup_declaration-notes" checked' in html
    assert "CONTINUUM_SETUP_USER_DECLARED" in html
    assert "Width evidence for setup qualification is incomplete" not in html
    data["action"] = "download"
    assert client.post("/proposed", data=data).get_json()["request"]["continuum_setup_declaration"]
    del data["continuum_setup_declaration"]
    assert "continuum_setup_declaration" not in client.post("/proposed", data=data).get_json()["request"]
    data.update(action="validate", continuum_setup_declaration="invalid")
    assert b"Input valid: <strong>No</strong>" in client.post("/proposed", data=data).data


def test_download_is_request_and_backend_ready(client):
    data = fields() | {"action": "download"}
    response = client.post("/proposed", data=data)
    document = response.get_json()
    assert set(document) == {"request", "search_options"}
    window = document["request"]["spectral_windows"][0]
    sensitivity = document["request"]["sensitivities"][0]
    assert window["center"] == {"value": "230.538", "unit": "GHz", "kind": "REST", "frame": "UNKNOWN"}
    assert sensitivity["window_ids"] == ["line-0"]
    assert sensitivity["smoothing_resolution"] == {"value": "20", "unit": "km/s"}
    assert sensitivity["rms"] == {"value": "0.3", "unit": "mJy/beam"}
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert result.is_valid and result.can_search
    assert response.headers["Cache-Control"] == "no-store"
    assert 'proposed-request.json' in response.headers["Content-Disposition"]


def test_mixed_intents_separate_sensitivities(client):
    data = MultiDict(fields())
    data.setlist("intents", ["CONTINUUM", "LINE"])
    data.setlist("sources", ["ARCHIVE", "QUEUE"])
    data.setlist("rows", [ROW, OTHER])
    data.update({"aggregate": "0.1", "aggregate_windows": "line-0 other",
                 "representative": "230", OTHER + "_id": "other",
                 OTHER + "_center": "228", OTHER + "_mode": "FDM",
                 OTHER + "_rms": "0.7", OTHER + "_resolution": "0.9765625",
                 OTHER + "_resolution_unit": "MHz"})
    data.setlist("action", ["download"])
    document = client.post("/proposed", data=data).get_json()
    aggregate, first, second = document["request"]["sensitivities"]
    assert aggregate["scope"] == "SETUP" and aggregate["basis"] == "AGGREGATE"
    assert aggregate["window_ids"] == ["line-0", "other"]
    assert first["window_ids"] == ["line-0"] and first["rms"]["value"] == "0.3"
    assert second["window_ids"] == ["other"] and second["rms"]["value"] == "0.7"
    assert second["smoothing_resolution"]["value"] == "0.9765625"


def test_add_remove_preserves_row_identity_and_raw_values(client):
    response = client.post("/proposed", data=fields() | {"action": "add"})
    html = response.get_data(as_text=True)
    rows = re.findall(r'name="rows" value="([a-z0-9]+)"', html)
    assert rows[0] == ROW and len(rows) == 2 and rows[1] != ROW
    assert 'value="230.538"' in html
    data = MultiDict(fields())
    data.setlist("rows", rows)
    data.setlist("action", ["remove:" + rows[1]])
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert re.findall(r'name="rows" value="([a-z0-9]+)"', html) == rows
    assert 'Confirm removal' in html
    assert 'value="230.538"' in html
    data.setlist("action", ["confirm-remove:" + rows[1]])
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert re.findall(r'name="rows" value="([a-z0-9]+)"', html) == [ROW]


@pytest.mark.parametrize("changes,path", [
    ({"ra": "bad"}, "request.position.ra"),
    ({ROW + "_rms": "-1"}, "request.sensitivities[0].rms"),
    ({"aggregate": "0.1", "aggregate_windows": "absent"}, "request.sensitivities[0].window_ids"),
])
def test_invalid_values_are_preserved_and_download_blocked(client, changes, path):
    response = client.post("/proposed", data=fields() | changes | {"action": "download"})
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert 'Input valid: <strong>No</strong>' in html
    assert path in html
    assert 'href="#' in html


def test_partial_input_remains_search_ready(client):
    data = fields()
    for key in (ROW + "_rms", ROW + "_resolution", "angular"):
        data.pop(key)
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'Input valid: <strong>Yes</strong>' in html
    assert 'Can search: <strong>Yes</strong>' in html
    assert 'MISSING' in html


def test_adapter_uses_backend_diagnostics_exactly():
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], ROW + "_rms": "bad"}
    document, result, issues = validate_form(values, [ROW])
    direct = validate_proposed_observation(document["request"], document["search_options"])
    assert json_value(result) == json_value(direct)
    assert [x["issue"] for x in issues] == list(direct.issues)
    assert any(x["field"] == ROW + "_rms" for x in issues)


def test_duplicate_window_and_unit_errors_use_validator(client):
    data = MultiDict(fields())
    data.setlist("rows", [ROW, OTHER])
    data.update({OTHER + "_id": "line-0", OTHER + "_center": "200", ROW + "_rms_unit": "Kelvin"})
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'Input valid: <strong>No</strong>' in html
    assert 'Kelvin (invalid selection)' in html
    assert 'window_id' in html


def test_transport_limits_and_escaping(client):
    data = MultiDict(fields())
    data.add("ra", "10")
    assert client.post("/proposed", data=data).status_code == 400
    assert client.post("/proposed", data=fields() | {"rows": "../bad"}).status_code == 400
    assert client.post("/proposed", data=fields() | {"action": "unsupported"}).status_code == 400
    html = client.post("/proposed", data=fields() | {"target_name": '<script>alert(1)</script>'}).data
    assert b'<script>alert' not in html
    assert client.post("/proposed", data=b'x' * (1024 * 1024 + 1), content_type='application/x-www-form-urlencoded').status_code == 413


def test_blank_line_rms_does_not_borrow_aggregate():
    values = fields() | {"intents": ["CONTINUUM", "LINE"], "sources": ["QUEUE"], "aggregate": "0.1", ROW + "_rms": ""}
    doc, _ = build_document(values, [ROW])
    assert doc["request"]["sensitivities"][1]["rms"] is None
    assert doc["request"]["sensitivities"][0]["rms"]["value"] == "0.1"


def test_equivalent_units_preserve_shared_exact_operands():
    from alma_duplicate.proposed_line import exact_request_quantity
    base = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"],
                       ROW + "_center_kind": "SKY", ROW + "_center": "230",
                       ROW + "_resolution": "0.9765625", ROW + "_resolution_unit": "MHz"}
    alternative = base | {ROW + "_center": "230000", ROW + "_center_unit": "MHz",
                          ROW + "_resolution": "976.5625", ROW + "_resolution_unit": "kHz",
                          ROW + "_rms": "0.0003", ROW + "_rms_unit": "Jy/beam"}
    a = validate_form(base, [ROW])[1]
    b = validate_form(alternative, [ROW])[1]
    assert a.is_valid and b.is_valid
    assert exact_request_quantity(a.request.sensitivities[0].smoothing_resolution) == exact_request_quantity(b.request.sensitivities[0].smoothing_resolution)
    assert a.request.sensitivities[0].rms.value == b.request.sensitivities[0].rms.value
    assert a.request.spectral_windows[0].center.quantity.value == b.request.spectral_windows[0].center.quantity.value


def test_missing_redshift_is_diagnostic_not_an_invented_conversion(client):
    data = fields() | {"redshift": ""}
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'SOURCE_REDSHIFT_REQUIRED' in html
    assert 'value="230.538"' in html


def test_continuum_usable_widths_and_aggregate_binding(client):
    data = MultiDict(fields())
    data.setlist("intents", ["CONTINUUM"])
    data.setlist("rows", [ROW, OTHER])
    for key in (ROW + "_rms", ROW + "_resolution", "redshift"):
        del data[key]
    data.setlist(ROW + "_center_kind", ["SKY"])
    data.update({"representative": "230", "aggregate": "0.1",
                 "aggregate_windows": "line-0 other", ROW + "_bandwidth": "1875",
                 ROW + "_bandwidth_kind": "USABLE", OTHER + "_id": "other",
                 OTHER + "_center": "228", OTHER + "_bandwidth": "1.875",
                 OTHER + "_bandwidth_unit": "GHz", OTHER + "_bandwidth_kind": "USABLE"})
    data.setlist("action", ["download"])
    document = client.post("/proposed", data=data).get_json()
    assert document["request"]["sensitivities"][0]["window_ids"] == ["line-0", "other"]
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert result.is_valid
    assert result.request.spectral_windows[0].bandwidth.value == result.request.spectral_windows[1].bandwidth.value


def test_aggregate_diagnostic_targets_contribution_selection():
    values = fields() | {"intents": ["CONTINUUM"], "sources": ["ARCHIVE"],
                         "aggregate": "0.1", "aggregate_windows": ["absent"]}
    _, result, issues = validate_form(values, [ROW])
    assert not result.is_valid
    assert any(entry["field"] == "aggregate_windows" and
               entry["issue"].path == "request.sensitivities[0].window_ids" for entry in issues)


def test_contribution_checkboxes_preserve_selection_through_editing(client):
    data = MultiDict(fields())
    data.setlist("rows", [ROW, OTHER])
    data.update({OTHER + "_id": "second", OTHER + "_center": "228",
                 "aggregate": "0.1"})
    data.setlist("aggregate_windows", ["line-0", "second"])
    data.setlist("action", ["cancel-remove"])
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'name="aggregate_windows" value="second" checked' in html
    assert re.findall(r'name="rows" value="([a-z0-9]+)"', html) == [ROW, OTHER]
    data.setlist("action", ["confirm-remove:" + OTHER])
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert 'Unavailable window: second' in html
    assert 'name="aggregate_windows" value="second" checked' in html
    # Removal preserves the declaration until the researcher explicitly revises it.
    data.setlist("rows", [ROW])
    data.setlist("action", ["download"])
    response = client.post("/proposed", data=data)
    assert response.mimetype == "text/html"
    assert 'href="#aggregate_windows"' in response.get_data(as_text=True)
    data.setlist("aggregate_windows", ["line-0"])
    document = client.post("/proposed", data=data).get_json()
    assert document["request"]["sensitivities"][0]["window_ids"] == ["line-0"]
    assert document["request"]["sensitivities"][0]["rms"]["value"] == "0.1"


def test_navigation_and_diagnostic_targets_exist(client):
    for url in ("/proposed", "/reports"):
        html = client.get(url).get_data(as_text=True)
        assert 'href="#candidates"' not in html
        assert 'href="#evidence"' not in html
        assert 'href="#result-guide"' not in html
        assert f'href="{url}" class="current" aria-current="page"' in html
    html = client.post("/proposed", data=fields() | {ROW + "_rms": "-1"}).get_data(as_text=True)
    ids = set(re.findall(r' id="([^"]+)"', html))
    assert len(ids) == len(re.findall(r' id="([^"]+)"', html))
    assert set(re.findall(r'href="#([^"]+)"', html)) <= ids
    assert 'aria-invalid="true"' in html
    assert 'All validation details' in html


def test_initial_form_has_no_required_window_rows(client):
    html = client.get("/proposed").get_data(as_text=True)
    assert 'name="rows"' not in html
    assert 'Spectral line requirements' in html
    assert 'Observation geometry: Single pointing.' in html
    assert html.index('id="line-requirements"') < html.index('id="sensitivities"') < html.index('id="windows"')
    html = client.post("/proposed", data={"setup_id": "setup-1", "intents": "LINE", "action": "purpose"}).get_data(as_text=True)
    rows = re.findall(r'name="rows" value="([a-z0-9]+)"', html)
    assert len(rows) == 1
    assert 'Window central frequency (REST or SKY)' in html
    assert 'Planned spectral resolution' in html
    assert 'Planned RMS at this resolution' in html
    assert f'name="{rows[0]}_id" value="{rows[0]}"' in html


@pytest.mark.parametrize("purpose,rule", [("CONTINUUM", "CONT-SETUP"), ("LINE", "LINE-COVERAGE")])
def test_no_windows_preserves_partial_request_and_missing_evidence(client, purpose, rule):
    data = {"setup_id": "setup-1", "ra": "201.365", "dec": "-43.019",
            "radius": "30", "sources": "ARCHIVE", "intents": purpose,
            "angular": "0.3", "representative": "230", "aggregate": "0.1",
            "action": "download"}
    response = client.post("/proposed", data=data)
    document = response.get_json()
    assert document["request"]["spectral_windows"] == []
    assert document["request"]["setup_complete"] is False
    assert document["request"]["representative_frequency"]["value"] == "230"
    sensitivity = document["request"]["sensitivities"][0]
    assert sensitivity["rms"]["value"] == "0.1" and sensitivity["window_ids"] == []
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert result.is_valid and result.can_search
    assert any(issue.category == "MISSING" and issue.rule_id == rule for issue in result.issues)
    html = client.post("/proposed", data=data | {"action": "validate"}).get_data(as_text=True)
    assert 'Input valid: <strong>Yes</strong>' in html
    assert 'Search readiness: <strong>READY</strong>' in html
    assert 'href="#windows"' in html


def test_purpose_update_preserves_mixed_inputs_and_does_not_validate(client):
    from html.parser import HTMLParser

    class FormValues(HTMLParser):
        def __init__(self):
            super().__init__()
            self.data = MultiDict()
            self.select = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "input" and attrs.get("name"):
                if attrs.get("type") != "checkbox" or "checked" in attrs:
                    self.data.add(attrs["name"], attrs.get("value", "on" if attrs.get("type") == "checkbox" else ""))
            elif tag == "select":
                self.select = attrs["name"]
            elif tag == "option" and "selected" in attrs:
                self.data.add(self.select, attrs["value"])

    data = MultiDict(fields())
    data.setlist("intents", ["LINE", "CONTINUUM"])
    data.update({"representative": "230000", "representative_unit": "MHz",
                 "aggregate": "0.0001", "aggregate_unit": "Jy/beam",
                 "continuum_setup_declaration": "on"})
    data.setlist("action", ["download"])
    original = client.post("/proposed", data=data).get_json()
    for purposes in (["CONTINUUM"], ["LINE"], [], ["LINE", "CONTINUUM"]):
        data.setlist("intents", purposes)
        data.setlist("action", ["purpose"])
        response = client.post("/proposed", data=data)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'data-validated="true"' not in html
        assert re.findall(r'name="rows" value="([a-z0-9]+)"', html) == [ROW]
        assert 'name="intents" value="LINE"' in html
        assert 'name="intents" value="CONTINUUM"' in html
        parsed = FormValues()
        parsed.feed(html)
        data = parsed.data
    data.setlist("action", ["download"])
    assert client.post("/proposed", data=data).get_json() == original


def test_purpose_update_adds_only_one_blank_line_and_keeps_continuum_windows(client):
    data = MultiDict({"setup_id": "setup-1", "intents": "LINE", "action": "purpose"})
    html = client.post("/proposed", data=data).get_data(as_text=True)
    rows = re.findall(r'name="rows" value="([a-z0-9]+)"', html)
    assert len(rows) == 1
    assert 'value="UNKNOWN" selected' in html
    assert 'data-validated="true"' not in html
    data.add("rows", rows[0])
    data.add(rows[0] + "_id", "retained-window")
    for purposes in (["CONTINUUM"], ["CONTINUUM", "LINE"]):
        data.setlist("intents", purposes)
        html = client.post("/proposed", data=data).get_data(as_text=True)
        assert re.findall(r'name="rows" value="([a-z0-9]+)"', html) == rows
        assert f'name="{rows[0]}_id" value="retained-window"' in html


def test_browser_defaults_auto_and_download_revalidates_without_hidden_radius(client):
    html = client.get('/proposed').get_data(as_text=True)
    assert 'name="radius_mode" value="AUTO"' in html
    assert 'name="radius"' not in html
    data = fields() | {'radius_mode': 'AUTO', 'action': 'download'}
    del data['radius']
    document = client.post('/proposed', data=data).get_json()
    assert document['search_options']['radius_mode'] == 'AUTO'
    assert 'radius' not in document['search_options']
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert result.is_valid and result.can_search
    data['action'] = 'validate'
    html = client.post('/proposed', data=data).get_data(as_text=True)
    assert 'Search readiness: <strong>READY</strong>' in html
    assert 'name="radius"' not in html
    data['radius'] = '30'
    html = client.post('/proposed', data=data).get_data(as_text=True)
    assert 'AUTO_RADIUS_CONFLICT' in html
    assert 'Conflicting explicit radius' in html and 'value="30"' in html
    data['radius'] = ''
    assert 'Input valid: <strong>Yes</strong>' in client.post('/proposed', data=data).get_data(as_text=True)
