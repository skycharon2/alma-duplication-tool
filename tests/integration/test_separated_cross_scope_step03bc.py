"""Step 03b-C: browser-to-typed-port acceptance, without new formal science.

The separated browser contract is deliberately not executable before the
versioned scientific evaluator is approved. Tests may inspect prepared
operands and CONT-SETUP window qualification, but must not promote these to a
formal LINE or Continuum duplication verdict.
"""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from alma_duplicate.assessment import AssessmentSources, AssessmentStatus, assess_observation
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.request_validation import _Validator, validate_proposed_observation
from alma_duplicate.rules.continuum_setup import (
    PORTAL_SCRIPT_V1, QUALIFIED, UNRESOLVED, qualify_window,
)
from alma_duplicate.separated_setup_input import parse_separated_setup
from alma_duplicate.ui import create_app
from alma_duplicate.ui.runs import BrowserAssessment
from tests.ui.test_separated_editor_step03bb import LINE, SPW, form

SECOND_SPW = "p123456abcdef"
SECOND_LINE = "labcdefabcdef"


@pytest.fixture
def client():
    app = create_app({
        "TESTING": True, "REPORT_DIRECTORY": None,
        "OFFLINE_ARCHIVE_REPLAY": None, "OFFLINE_QUEUE_CSV": None,
        "LIVE_ARCHIVE": False,
    })
    with app.test_client() as browser:
        yield browser
    app.extensions["assessment_runs"].close()


def export(client, data):
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == "application/json", response.get_data(as_text=True)
    return response.get_json()


def typed(document):
    validator = _Validator()
    raw = validator.snapshot(document["request"], "request")
    operands = parse_separated_setup(validator, raw)
    assert operands is not None
    assert not [issue for issue in validator.issues if issue.category == "ERROR"], validator.issues
    return operands


def check_fail_closed(document):
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert not result.is_valid and not result.can_search
    assert result.request is None and result.search_options is None
    assert [issue.code for issue in result.errors] == ["SEPARATED_INPUT_NOT_EXECUTABLE"]


def spw_pair_form(*, geometry="SINGLE_POINTING", complete=False):
    data = form("download", spws=(SPW, SECOND_SPW), geometry=geometry)
    data[SECOND_SPW + "_linked"] = ""
    data[SECOND_SPW + "_center"] = "225.1"  # Equal frequency must not merge IDs.
    data[SECOND_SPW + "_center_kind"] = "SKY"
    data[SECOND_SPW + "_bandwidth"] = "2000"
    data[SECOND_SPW + "_bandwidth_kind"] = "NOMINAL"
    if complete:
        data["physical_spw_inventory_complete"] = "on"
    return data


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
@pytest.mark.parametrize("complete", [False, True])
def test_browser_export_keeps_line_and_physical_operands_independent(client, geometry, complete):
    document = export(client, spw_pair_form(geometry=geometry, complete=complete))
    request = document["request"]
    assert request["geometry"] == geometry
    if geometry == "MOSAIC":
        assert request["position"] is None
    else:
        assert request["position"]["frame"] == "ICRS"
    assert request["physical_spw_inventory_complete"] is complete
    assert not {"spectral_windows", "sensitivities", "setup_complete", "line_evaluation_scope"} & set(request)
    assert len(request["line_requirements"]) == 1
    assert len(request["physical_spw_evidence"]) == 2

    operands = typed(document)
    windows, rms = operands.line_comparison_operands
    assert [w.window_id for w in windows] == [LINE]
    assert len(rms) == 1 and rms[0].window_ids == (LINE,)
    assert windows[0].bandwidth is None
    prepared = prepare_line_window(windows[0], rms, None)
    assert prepared.sensitivity_id == "line:" + LINE
    assert prepared.sky_frequency_ghz_exact is not None
    assert prepared.planned_resolution_kms_exact is not None

    assert [w.window_id for w in operands.continuum_window_evidence] == [SPW, SECOND_SPW]
    assert [link.line_requirement_id for link in operands.physical_links] == [LINE, None]
    assert len(operands.continuum_window_evidence) == 2  # No linked SPW clone.
    assert [qualify_window(w)[0] for w in operands.continuum_window_evidence] == [
        QUALIFIED, UNRESOLVED,
    ]
    assert [qualify_window(w, nominal_conversion=PORTAL_SCRIPT_V1)[0]
            for w in operands.continuum_window_evidence] == [QUALIFIED, QUALIFIED]
    assert operands.physical_inventory_complete is complete
    check_fail_closed(document)


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_shared_redshift_prepares_rest_window_and_missing_redshift_blocks_export(client, geometry):
    data = form("download", geometry=geometry, redshift="0.024", **{
        LINE + "_center_kind": "REST",
    })
    document = export(client, data)
    operands = typed(document)
    prepared = prepare_line_window(
        operands.line_windows[0], operands.line_sensitivities,
        float(document["request"]["source_redshift"]),
    )
    assert prepared.sky_frequency_ghz_exact is not None
    check_fail_closed(document)

    del data["redshift"]
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "LINE_FREQUENCY_UNRESOLVED" in response.text


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_second_explicit_line_keeps_own_rms_and_never_borrows_spw_bandwidth(client, geometry):
    data = spw_pair_form(geometry=geometry)
    data.add("line_rows", SECOND_LINE)
    data[SECOND_LINE + "_id"] = SECOND_LINE
    data[SECOND_LINE + "_center"] = "240"
    data[SECOND_LINE + "_center_unit"] = "GHz"
    data[SECOND_LINE + "_center_kind"] = "SKY"
    data[SECOND_LINE + "_mode"] = "TDM"  # Complete input; FDM science is not invoked.
    data[SECOND_LINE + "_resolution"] = "10"
    data[SECOND_LINE + "_resolution_unit"] = "km/s"
    data[SECOND_LINE + "_rms"] = "0.7"
    data[SECOND_LINE + "_rms_unit"] = "mJy/beam"
    document = export(client, data)
    operands = typed(document)
    windows, sensitivities = operands.line_comparison_operands
    assert [window.window_id for window in windows] == [LINE, SECOND_LINE]
    assert [s.window_ids for s in sensitivities] == [(LINE,), (SECOND_LINE,)]
    assert [str(s.rms.raw_value) for s in sensitivities] == ["0.3", "0.7"]
    assert windows[1].correlator_mode == "TDM"
    assert len(operands.continuum_window_evidence) == 2
    for window, sensitivity in zip(windows, sensitivities):
        planned = prepare_line_window(window, (sensitivity,), None)
        assert planned.sensitivity_id == "line:" + window.window_id
    check_fail_closed(document)


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_missing_second_line_rms_blocks_export_even_with_optional_spws(client, geometry):
    data = spw_pair_form(geometry=geometry)
    data.add("line_rows", SECOND_LINE)
    data[SECOND_LINE + "_id"] = SECOND_LINE
    data[SECOND_LINE + "_center"] = "240"
    data[SECOND_LINE + "_mode"] = "FDM"
    data[SECOND_LINE + "_resolution"] = "20"
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "LINE_RMS_REQUIRED" in response.text
    assert "request.line_requirements[1].rms" in response.text


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_continuum_only_or_mixed_intents_use_physical_port_not_line_clone(client, geometry):
    document = export(client, spw_pair_form(geometry=geometry))
    mixed = deepcopy(document)
    mixed["request"]["intents"] = ["LINE", "CONTINUUM"]
    mixed_inputs = typed(mixed)
    assert len(mixed_inputs.line_comparison_operands[0]) == 1
    assert len(mixed_inputs.continuum_window_evidence) == 2
    check_fail_closed(mixed)

    continuum_only = deepcopy(document)
    continuum_only["request"]["intents"] = ["CONTINUUM"]
    continuum_only["request"]["line_requirements"] = []
    continuum_only["request"]["physical_spw_evidence"][0].pop("linked_line_requirement_id")
    cont_inputs = typed(continuum_only)
    assert cont_inputs.line_comparison_operands == ((), ())
    assert len(cont_inputs.continuum_window_evidence) == 2
    assert [w.window_id for w in cont_inputs.continuum_window_evidence] == [SPW, SECOND_SPW]
    check_fail_closed(continuum_only)


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
@pytest.mark.parametrize("complete", [False, True])
def test_form_and_shared_assessment_do_not_run_sources_or_issue_negative_verdict(
    client, monkeypatch, geometry, complete,
):
    def forbidden(*args, **kwargs):
        pytest.fail("Separated contract must not execute any data source")

    monkeypatch.setattr(BrowserAssessment, "assess", forbidden)
    monkeypatch.setattr(BrowserAssessment, "assess_mosaic", forbidden)
    data = spw_pair_form(geometry=geometry, complete=complete)
    data["action"] = "assess"  # Explicit hostile/unsupported POST bypassing hidden UI.
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Assessment is unavailable" in response.text

    data["action"] = "download"
    document = export(client, data)
    sources = AssessmentSources(archive_kind="LIVE", archive_provider=forbidden)
    result = assess_observation(
        document["request"], document["search_options"], sources=sources,
        mosaic=SimpleNamespace() if geometry == "MOSAIC" else None,
    )
    assert result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
    assert result.document is None  # No result, hence no formal negative LINE verdict.
    assert any(issue.code == "SEPARATED_INPUT_NOT_EXECUTABLE" for issue in result.validation.errors)


def test_removing_optional_spw_keeps_line_ids_and_does_not_synthesize_new_evidence(client):
    data = form("remove-spw:" + SPW, spws=(SPW,))
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert f'name="line_rows" value="{LINE}"' in response.text
    assert 'name="spw_rows"' not in response.text
    assert "LINE requirement 2" not in response.text


def test_deleting_linked_requirement_requires_unlink_not_orphaned_physical_id(client):
    response = client.post("/proposed/separated", data=form(
        "remove-line:" + LINE, spws=(SPW,),
    ))
    assert response.status_code == 200
    assert "LINKED_LINE_REMOVAL_BLOCKED" in response.text
    assert f'name="line_rows" value="{LINE}"' in response.text
    assert f'name="spw_rows" value="{SPW}"' in response.text


def test_legacy_input_still_uses_legacy_validator_without_separated_contract():
    from tests.integration.test_line_evaluation import sky_request
    old = sky_request(225.134765625)
    validated = validate_proposed_observation(old["request"], old["search_options"])
    assert validated.is_valid and validated.can_search
    assert validated.request is not None
    assert "line_input_contract" not in validated.request.raw_input
