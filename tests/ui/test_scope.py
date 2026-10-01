"""Observation selection preserves input without enabling unsupported execution."""

from html.parser import HTMLParser

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.ui import create_app
from alma_duplicate.ui.runs import OfflineAssessment


class FormValues(HTMLParser):
    """Round-trip successful form controls, including retained scientific values."""

    def __init__(self, html):
        super().__init__()
        self.data = MultiDict()
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") and "disabled" not in attrs:
            if attrs.get("type") != "checkbox" or "checked" in attrs:
                self.data.add(attrs["name"], attrs.get("value", "on"))
        elif tag == "select":
            self.select = attrs["name"]
        elif tag == "option" and "selected" in attrs:
            self.data.add(self.select, attrs["value"])


@pytest.fixture
def client(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported observation reached execution")

    monkeypatch.setattr(OfflineAssessment, "assess", forbidden)
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None,
                       "OFFLINE_ARCHIVE_REPLAY": "/must-not-read.json",
                       "OFFLINE_QUEUE_CSV": "/must-not-read.csv"}).test_client()


def form():
    return MultiDict({
        "setup_id": "setup-1", "target_kind": "FIXED", "geometry": "SINGLE_POINTING",
        "ra": "201.365", "dec": "-43.019", "radius": "30", "sources": "ARCHIVE",
        "intents": "LINE", "rows": "w123456abcdef", "w123456abcdef_id": "line-0",
        "w123456abcdef_center": "230.538", "w123456abcdef_center_kind": "REST",
        "redshift": "0.024", "w123456abcdef_resolution": "20",
        "w123456abcdef_rms": "0.3", "w123456abcdef_mode": "FDM",
        "angular": "0.3", "aggregate": "0.1", "representative": "230",
        "aggregate_windows": "line-0", "continuum_setup_declaration": "on",
        "action": "download",
    })


@pytest.mark.parametrize("kind,geometry,readiness", [
    ("FIXED", "MOSAIC", "UNSUPPORTED"),
    ("MOVING", "SINGLE_POINTING", "UNSUPPORTED"),
    ("MOVING", "MOSAIC", "UNSUPPORTED"),
    ("SUN", "SINGLE_POINTING", "NOT_APPLICABLE"),
    ("SUN", "MOSAIC", "NOT_APPLICABLE"),
])
def test_selection_export_and_forged_assess_are_safe(client, kind, geometry, readiness):
    data = form()
    data["target_kind"], data["geometry"] = kind, geometry
    response = client.post("/proposed", data=data)
    document = response.get_json()
    assert document["request"]["target_kind"] == kind
    assert document["request"]["geometry"] == geometry
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert result.is_valid and not result.can_search
    assert result.search_readiness.value == readiness
    data["action"] = "assess"
    response = client.post("/proposed", data=data)
    assert response.status_code == 200 and "Location" not in response.headers
    html = response.get_data(as_text=True)
    if kind == "SUN":
        assert "Solar observations are exempt from duplication checking under Appendix A" in html
        assert 'value="assess"' not in html
        assert '<details class="solar-retained" id="solar-retained">' in html
    else:
        assert "This observation type cannot be assessed" in html
        assert 'disabled aria-describedby="scope-support"' in html
    assert 'value="230.538"' in html
    assert f'Search readiness: <strong>{readiness}</strong>' in html


def test_scope_round_trip_preserves_mixed_inputs_and_has_no_validation(client, monkeypatch):
    import alma_duplicate.ui.app as app_module

    data = form()
    data.setlist("intents", ["LINE", "CONTINUUM"])
    original = client.post("/proposed", data=data).get_json()
    with monkeypatch.context() as patch:
        patch.setattr(app_module, "validate_form", lambda *args: pytest.fail("Scope change validated"))
        for kind, geometry in [("MOVING", "MOSAIC"), ("SUN", "SINGLE_POINTING"),
                               ("FIXED", "SINGLE_POINTING")]:
            data["target_kind"], data["geometry"], data["action"] = kind, geometry, "scope"
            html = client.post("/proposed", data=data).get_data(as_text=True)
            assert "data-scope-updated" in html and 'data-validated="true"' not in html
            assert "Update observation type" in html  # No-JavaScript action.
            data = FormValues(html).data
    data["action"] = "download"
    assert client.post("/proposed", data=data).get_json() == original


@pytest.mark.parametrize("kind", ["MOVING", "SUN"])
def test_nonfixed_blank_position_is_absent_but_partial_position_is_validated(client, kind):
    data = {"target_kind": kind, "geometry": "SINGLE_POINTING", "setup_id": "setup-1",
            "action": "download"}
    response = client.post("/proposed", data=data)
    assert response.get_json()["request"]["position"] is None
    response = client.post("/proposed", data=data | {"ra": "bad"})
    assert response.mimetype == "text/html"
    assert b'Input valid: <strong>No</strong>' in response.data


@pytest.mark.parametrize("key,value", [("target_kind", "COMET"), ("geometry", "OTHER")])
def test_unknown_scope_is_not_silently_replaced(client, key, value):
    data = form()
    data[key] = value
    for action in ("assess", "download"):
        data["action"] = action
        response = client.post("/proposed", data=data)
        assert response.mimetype == "text/html"
        assert b'Input valid: <strong>No</strong>' in response.data
        assert f'selected value="{value}"' in response.get_data(as_text=True)


def test_type_specific_location_guidance(client):
    data = form()
    data["action"] = "scope"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert "search radius below controls candidate retrieval" in html
    data["geometry"] = "MOSAIC"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert "more than 50% of the proposed pointings" in html
    assert "Pointing-list input and coverage evaluation are not implemented" in html
    data["target_kind"] = "MOVING"
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert '<label for="target_name">Moving-object name</label>' in html
    assert "Object-name matching is not implemented" in html
    assert "<summary>Retained coordinates</summary>" in html
    assert 'name="ra" value="201.365"' in html


def test_requested_windows_and_alternative_conditions_match_wire_contract(client):
    data = form()
    data["action"] = "purpose"
    data.setlist("intents", ["LINE", "CONTINUUM"])
    html = client.post("/proposed", data=data).get_data(as_text=True)
    assert "Requested window 1" in html
    assert "Requested line 1" not in html
    assert "Window central frequency (REST or SKY)" in html
    assert "every window need not pass" in html
    assert "does not require both spectral routes to pass" in html
    assert "interprets that bandwidth as usable bandwidth" in html
    data["action"] = "download"
    document = client.post("/proposed", data=data).get_json()
    assert len(document["request"]["spectral_windows"]) == 1
    assert document["request"]["spectral_windows"][0]["center"]["value"] == "230.538"
