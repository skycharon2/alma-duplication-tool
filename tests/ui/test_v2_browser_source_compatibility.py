"""Explicit V2 unsupported sources are blocked without corrupting the input schema.

Offline Flask tests: no Archive/Queue queries or scientific verdicts are run.
Requires the first-step Single Pointing compatibility patch (2ca3519).
"""

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.separated_setup_input import SEPARATED_OBSERVATION_CONTRACT
from alma_duplicate.ui import create_app
from alma_duplicate.ui.proposed import build_document, validate_form
from tests.ui.test_default_single_pointing_contract import continuum_form


@pytest.fixture
def client():
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None,
                       "OFFLINE_ARCHIVE_REPLAY": "/must-not-read.json",
                       "OFFLINE_QUEUE_CSV": "/must-not-read.csv"}).test_client()


def v2_continuum(sources=("ARCHIVE", "QUEUE")):
    values = continuum_form()
    # WerkZeug MultiDict cannot convert a key holding an empty list to dict.
    # Missing source selection is represented by an absent key in a real POST.
    if sources:
        values.setlist("sources", list(sources))
    else:
        values.pop("sources", None)
    values["normal_form_version"] = "2"
    values["normal_line_records"] = "1"
    values["frequency_local_redshift"] = "1"
    values["representative_kind"] = "REST"
    values["continuum_redshift"] = "0.5"
    return values


def unpack(values):
    rows = values.getlist("rows")
    data = values.to_dict()
    for key in ("sources", "intents", "spw_rows", "aggregate_windows"):
        data[key] = values.getlist(key)
    return data, rows


def test_unsupported_v2_preserves_real_schema_and_local_redshift():
    values, rows = unpack(v2_continuum())
    document, bindings = build_document(values, rows)
    request = document["request"]
    assert request["line_input_contract"] == SEPARATED_OBSERVATION_CONTRACT
    assert "spectral_windows" not in request
    assert "sensitivities" not in request
    assert "setup_complete" not in request
    assert request["continuum_requirement"]["source_redshift"] == "0.5"
    assert request["continuum_requirement"]["rms"]["value"] == "0.01"
    assert document["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
    assert bindings["search_options.sources"] == "sources"


@pytest.mark.parametrize("sources", [(), ("QUEUE",), ("ARCHIVE", "QUEUE")])
def test_unsupported_v2_is_specific_blocked_issue(sources):
    values, rows = unpack(v2_continuum(sources))
    _, result, issues = validate_form(values, rows)
    assert not result.is_valid
    assert not result.can_search
    scope = [item for item in issues if item["issue"].code == "BROWSER_V2_SCOPE_UNSUPPORTED"]
    assert len(scope) == 1
    assert scope[0]["field"] == "sources"
    assert "Archive-only" in scope[0]["issue"].message
    assert not any(item["issue"].code == "INVALID_CHOICE"
                   and item["issue"].path == "request.line_input_contract" for item in issues)
    assert not any("Separated input must not include legacy" in item["issue"].message
                   for item in issues)


@pytest.mark.parametrize("action", ["validate", "download", "assess"])
def test_unsupported_v2_actions_retain_inputs_and_never_run(client, monkeypatch, action):
    from alma_duplicate.ui.runs import BrowserAssessment

    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported V2 request attempted a source assessment")

    monkeypatch.setattr(BrowserAssessment, "assess", forbidden)
    data = v2_continuum()
    data["action"] = action
    response = client.post("/proposed", data=data)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    # The UI intentionally includes issue codes in its diagnostic details.
    # Verify that the specific error is visible rather than hiding its code.
    assert "BROWSER_V2_SCOPE_UNSUPPORTED" in html
    assert "UNSUPPORTED_BROWSER_LINE_SCOPE" not in html
    assert "Separated input must not include legacy" not in html
    assert "This optional separated V2 editor currently supports Archive-only assessment" in html
    assert 'Input valid: <strong>No</strong>' in html
    assert 'name="normal_line_records" value="1"' in html
    assert 'name="continuum_redshift" value="0.5"' in html
    assert 'name="sources" value="QUEUE" checked' in html


def test_physical_spw_selection_not_mislabeled_on_unsupported_sources(client):
    values = v2_continuum()
    spw = "w111111111111"
    values.add("spw_rows", spw)
    values[spw + "_id"] = "physical-a"
    values[spw + "_bandwidth"] = "2000"
    values[spw + "_bandwidth_kind"] = "USABLE"
    values.add("aggregate_windows", "physical-a")
    values["action"] = "validate"
    html = client.post("/proposed", data=values).get_data(as_text=True)
    assert 'name="spw_rows" value="w111111111111"' in html
    assert 'name="aggregate_windows" value="physical-a"' in html
    assert 'Unavailable window: physical-a' not in html
    assert "This optional separated V2 editor currently supports Archive-only assessment" in html


def test_explicit_v2_version_does_not_fall_back_if_hidden_flag_missing():
    data = v2_continuum()
    data.pop("normal_line_records")
    values, rows = unpack(data)
    doc, _, _ = validate_form(values, rows)
    assert doc["request"]["line_input_contract"] == SEPARATED_OBSERVATION_CONTRACT


def test_archive_only_v2_and_default_legacy_stay_distinct():
    archive, rows = unpack(v2_continuum(("ARCHIVE",)))
    doc, result, _ = validate_form(archive, rows)
    assert doc["request"]["line_input_contract"] == SEPARATED_OBSERVATION_CONTRACT
    assert not any(issue.code == "BROWSER_V2_SCOPE_UNSUPPORTED" for issue in result.issues)

    legacy, rows = unpack(continuum_form())
    doc, result, _ = validate_form(legacy, rows)
    assert "line_input_contract" not in doc["request"]
    assert result.is_valid
    assert doc["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
