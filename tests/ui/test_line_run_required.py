"""Step 03: strict browser Run gate; no change to shared legacy science."""

import pytest

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.ui.proposed import validate_form
from tests.ui.test_proposed import ROW, fields
from tests.ui.test_runs import config, line_form
from tests.ui.test_mosaic_execution import (
    browser as mosaic_browser,  # noqa: F401 - pytest discovers this imported fixture
    form as mosaic_form, upload as upload_mosaic,
)


@pytest.mark.parametrize("remove,code,field", [
    ("center", "LINE_SKY_FREQUENCY_REQUIRED", ROW + "_center"),
    ("mode", "LINE_MODE_REQUIRED", ROW + "_mode"),
    ("resolution", "LINE_RESOLUTION_REQUIRED", ROW + "_resolution"),
    ("rms", "LINE_RMS_REQUIRED", ROW + "_rms"),
])
def test_each_missing_line_field_blocks_only_browser_run(remove, code, field):
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": ""}
    values.pop(ROW + "_" + remove)
    document, ordinary, _ = validate_form(values, [ROW])
    assert ordinary.is_valid and ordinary.can_search
    run_document, run, issues = validate_form(values, [ROW], require_line_complete=True)
    assert run_document == document
    assert not run.is_valid and not run.can_search
    assert any(item["issue"].code == code and item["field"] == field for item in issues)
    # CLI/API continue preserving missing evidence rather than rejecting it.
    shared = validate_proposed_observation(document["request"], document["search_options"])
    assert shared.is_valid and shared.can_search


def test_rest_frequency_requires_redshift_only_for_browser_run():
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": ""}
    values.pop("redshift")
    _, ordinary, _ = validate_form(values, [ROW])
    assert ordinary.is_valid and ordinary.can_search
    _, result, issues = validate_form(values, [ROW], require_line_complete=True)
    assert not result.is_valid
    assert any(item["field"] == "redshift" and item["issue"].code == "LINE_REST_REDSHIFT_REQUIRED"
               for item in issues)
    values[ROW + "_center_kind"] = "SKY"
    _, result, _ = validate_form(values, [ROW], require_line_complete=True)
    assert result.is_valid and result.can_search


def test_no_window_blocks_run_not_old_request_validation():
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": ""}
    _, old, _ = validate_form(values, [])
    assert old.is_valid and old.can_search
    _, result, issues = validate_form(values, [], require_line_complete=True)
    assert not result.is_valid
    assert any(x["field"] == "line_requirements" and x["issue"].code == "LINE_WINDOW_REQUIRED"
               for x in issues)


def test_every_line_row_is_checked_not_just_the_first():
    other = "wabcdef123456"
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": ""}
    values.update({other + "_id": "line-1", other + "_center": "240",
                   other + "_center_kind": "SKY", other + "_mode": "FDM",
                   other + "_rms": "0.3"})
    _, result, issues = validate_form(values, [ROW, other], require_line_complete=True)
    assert not result.is_valid
    assert any(x["field"] == other + "_resolution" and x["issue"].code == "LINE_RESOLUTION_REQUIRED"
               for x in issues)
    assert not any(x["issue"].code == "LINE_RESOLUTION_REQUIRED" and x["field"] == ROW + "_resolution"
                   for x in issues)


def test_complete_main_line_without_bandwidth_or_inventory_claim_is_run_ready():
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": ""}
    document, result, issues = validate_form(values, [ROW], require_line_complete=True)
    assert result.is_valid and result.can_search
    assert not any(x["issue"].category == "ERROR" for x in issues)
    assert "bandwidth" not in document["request"]["spectral_windows"][0]
    assert document["request"]["setup_complete"] is False
    assert "line_evaluation_scope" not in document["request"]


def test_known_tdm_is_complete_input_not_valid_fdm_science():
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"], "setup_complete": "",
                         ROW + "_mode": "TDM"}
    _, result, issues = validate_form(values, [ROW], require_line_complete=True)
    assert result.is_valid and result.can_search
    assert not any(x["issue"].code == "LINE_MODE_REQUIRED" for x in issues)


def test_continuum_only_does_not_trigger_line_run_gate():
    values = fields() | {"intents": ["CONTINUUM"], "sources": ["ARCHIVE"], "setup_complete": ""}
    _, ordinary, _ = validate_form(values, [], require_line_complete=False)
    _, run, issues = validate_form(values, [], require_line_complete=True)
    assert run.is_valid == ordinary.is_valid
    assert not any(x["issue"].code.startswith("LINE_") and x["issue"].category == "ERROR"
                   for x in issues)


@pytest.mark.parametrize("field", [ROW + "_center", ROW + "_mode", ROW + "_resolution", ROW + "_rms"])
def test_single_point_run_never_calls_source_with_incomplete_line(monkeypatch, field):
    from alma_duplicate.ui import create_app
    from alma_duplicate.ui import runs as execution
    monkeypatch.setattr(execution.BrowserAssessment, "assess",
                        lambda *a, **kw: pytest.fail("single-point provider invoked"))
    client = create_app(config()).test_client()
    form = line_form()
    del form[field]
    response = client.post("/proposed", data=form)
    assert response.status_code == 200
    assert "Assessment was not run" in response.text
    assert "LINE" in response.text
    assert client.get("/runs/unknown").status_code == 404


@pytest.mark.parametrize("field", [ROW + "_center", ROW + "_mode", ROW + "_resolution", ROW + "_rms"])
def test_mosaic_run_never_calls_source_with_incomplete_line(request, monkeypatch, field):
    from alma_duplicate.ui import runs as execution
    client, calls = request.getfixturevalue("mosaic_browser")
    token = upload_mosaic(client)
    monkeypatch.setattr(execution.BrowserAssessment, "assess_mosaic",
                        lambda *a, **kw: pytest.fail("Mosaic provider invoked"))
    form = mosaic_form() | dict(action="assess", mosaic_upload_token=token)
    del form[field]
    response = client.post("/proposed", data=form)
    assert response.status_code == 200
    assert "Assessment was not run" in response.text
    assert not calls


def test_mixed_purpose_line_requirement_is_still_required():
    values = fields() | {"intents": ["LINE", "CONTINUUM"], "sources": ["ARCHIVE"], "setup_complete": ""}
    values.pop(ROW + "_rms")
    _, result, issues = validate_form(values, [ROW], require_line_complete=True)
    assert not result.is_valid
    assert any(x["issue"].code == "LINE_RMS_REQUIRED" for x in issues)


def test_single_point_complete_line_runs_without_optional_inventory():
    from alma_duplicate.ui import create_app
    client = create_app(config()).test_client()
    form = line_form()
    form.setlist("setup_complete", [""])
    response = client.post("/proposed", data=form)
    assert response.status_code == 303, response.text
    request = client.get(response.location + "/download/request").get_json()["request"]
    assert request["setup_complete"] is False
    assert "bandwidth" not in request["spectral_windows"][0]
    assert "line_evaluation_scope" not in request


def test_mosaic_complete_line_runs_without_optional_inventory(request):
    client, calls = request.getfixturevalue("mosaic_browser")
    token = upload_mosaic(client)
    form = mosaic_form() | dict(action="assess", mosaic_upload_token=token, setup_complete="")
    response = client.post("/proposed", data=form)
    assert response.status_code == 303, response.text
    assert calls, "Valid Mosaic LINE submission must reach discovery"
    request = client.get(response.location + "/download/request").get_json()["request"]
    assert request["physical_spw_inventory_complete"] is False
    assert request["line_input_contract"] == "SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1"
    assert "setup_complete" not in request
    assert request["physical_spw_evidence"] == []
    assert len(request["line_requirements"]) == 1
