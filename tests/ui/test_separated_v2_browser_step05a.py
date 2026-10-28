"""Step 05A: opt-in separated LINE V2 browser surface and source isolation.

All source examples are local recorded Guide B data. Never touch live Archive.
"""

from copy import deepcopy

import pytest

from alma_duplicate.ui import create_app
from tests.integration.test_line_preparation import EXAMPLE
from tests.ui.test_separated_editor_step03bb import LINE, SPW, form


@pytest.fixture
def make_client():
    apps = []

    def make(**overrides):
        options = {
            "TESTING": True,
            "REPORT_DIRECTORY": None,
            "OFFLINE_ARCHIVE_REPLAY": None,
            "OFFLINE_QUEUE_CSV": None,
            "LIVE_ARCHIVE": False,
            "LIVE_AQ": False,
            "SUBMITTED_LINE_V2_UI_ENABLED": False,
        }
        options.update(overrides)
        app = create_app(options)
        apps.append(app)
        return app.test_client()

    yield make
    for app in apps:
        app.extensions["assessment_runs"].close()


def _replay_client(make_client):
    return make_client(
        SUBMITTED_LINE_V2_UI_ENABLED=True,
        OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE / "archive/manifest.json"),
    )


@pytest.mark.parametrize("action", ["assess-v2", "download-v2"])
def test_opt_in_flag_is_disabled_by_default_and_cannot_be_overridden_by_post(make_client, monkeypatch, action):
    client = make_client()
    assert b"Run V2 Archive LINE" not in client.get("/proposed/separated").data
    def forbidden(*a, **kw):
        pytest.fail("disabled runner accessed")
    monkeypatch.setattr("alma_duplicate.ui.separated_v2.run_single_v2", forbidden)
    response = client.post("/proposed/separated", data=form(action))
    assert response.status_code == 200
    assert "SUBMITTED_LINE_V2_UI_DISABLED" in response.text
    assert response.mimetype == "text/html"


def test_enabled_ui_runs_reference_bound_real_replay_and_renders_pairs(make_client):
    client = _replay_client(make_client)
    assert b"Run V2 Archive LINE" in client.get("/proposed/separated").data
    response = client.post("/proposed/separated", data=form("assess-v2"))
    assert response.status_code == 200
    assert "V2 Archive candidate evaluation" in response.text
    assert "archive_line_context_submitted_or_2" in response.text
    assert "LINE-COVERAGE" in response.text
    assert LINE in response.text
    assert "No Archive-wide non-duplication conclusion" in response.text


def test_v2_download_retains_original_wire_and_candidate_provenance(make_client):
    client = _replay_client(make_client)
    response = client.post("/proposed/separated", data=form("download-v2", spws=(SPW,)))
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert "attachment" in response.headers["Content-Disposition"]
    document = response.get_json()
    assert document["report_version"] == "7"
    assert document["request"]["raw"]["line_input_contract"] == "SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1"
    assert len(document["request"]["raw"]["line_requirements"]) == 1
    assert len(document["request"]["raw"]["physical_spw_evidence"]) == 1
    assert document["v2_science"]["search_wide_duplication_verdict"] == "NOT_EVALUATED"
    assert document["assessment"] == "NOT_AGGREGATED"
    assert "ARCHIVE" in document["sources"]
    assert document["v2_science"]["line_context_method_version"] == "archive_line_context_submitted_or_2"
    assert all("reference" in context and "line_pairs" in context
               for context in document["context_evaluations"])


@pytest.mark.parametrize("action", ["assess-v2", "download-v2"])
def test_invalid_line_and_unsupported_mosaic_never_start_archive(make_client, monkeypatch, action):
    client = _replay_client(make_client)
    def forbidden(*a, **kw):
        pytest.fail("invalid request touched Archive")
    monkeypatch.setattr("alma_duplicate.ui.separated_v2.run_single_v2", forbidden)
    missing_rms = form(action)
    del missing_rms[LINE + "_rms"]
    result = client.post("/proposed/separated", data=missing_rms)
    assert result.status_code == 200
    assert "LINE_RMS_REQUIRED" in result.text
    mosaic = client.post("/proposed/separated", data=form(action, geometry="MOSAIC"))
    assert mosaic.status_code == 200
    assert "SUBMITTED_LINE_V2_SINGLE_ONLY" in mosaic.text
    assert mosaic.mimetype == "text/html"


def test_missing_archive_and_unapproved_aq_config_do_not_execute(make_client):
    no_source = make_client(SUBMITTED_LINE_V2_UI_ENABLED=True)
    no_source_response = no_source.post("/proposed/separated", data=form("assess-v2"))
    assert no_source_response.status_code == 200
    assert "SUBMITTED_LINE_V2_REQUIRES_ONE_ARCHIVE_SOURCE" in no_source_response.text

    with_aq = make_client(
        SUBMITTED_LINE_V2_UI_ENABLED=True, LIVE_ARCHIVE=True, LIVE_AQ=True,
    )
    result = with_aq.post("/proposed/separated", data=form("assess-v2"))
    assert result.status_code == 200
    assert "SUBMITTED_LINE_V2_AQ_NOT_SUPPORTED" in result.text


def test_existing_legacy_and_separated_validation_unchanged(make_client):
    client = _replay_client(make_client)
    assert client.get("/proposed").status_code == 200
    assert client.post("/proposed/separated", data=form("validate")).status_code == 200
    assert client.post("/proposed/separated", data=form("download")).mimetype == "application/json"
    invalid = deepcopy(form("assess-v2"))
    invalid["setup_complete"] = "on"
    assert client.post("/proposed/separated", data=invalid).status_code == 400
