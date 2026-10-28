"""Step 03b-B browser editor: independent row lifecycles and fail-closed export."""

import re

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.ui import create_app
from alma_duplicate.ui.separated_editor import build_separated_document

LINE = "l123456abcdef"
SPW = "pabcdef123456"


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "REPORT_DIRECTORY": None,
                      "OFFLINE_ARCHIVE_REPLAY": None, "OFFLINE_QUEUE_CSV": None,
                      "LIVE_ARCHIVE": False})
    with app.test_client() as c:
        yield c
    app.extensions["assessment_runs"].close()


def form(action="validate", *, rows=(LINE,), spws=(), **changes):
    data = MultiDict({
        "action": action, "setup_id": "setup-1", "target_name": "Case B",
        "geometry": "SINGLE_POINTING", "ra": "201.365", "dec": "-43.019",
        "ra_format": "DEG", "dec_format": "DEG", "angular": "0.3",
        "angular_unit": "arcsec", "radius": "30", "radius_unit": "arcsec",
    })
    for row in rows:
        data.add("line_rows", row)
        data[row + "_id"] = row
        data[row + "_center"] = "225.1"
        data[row + "_center_unit"] = "GHz"
        data[row + "_center_kind"] = "SKY"
        data[row + "_mode"] = "FDM"
        data[row + "_resolution"] = "20"
        data[row + "_resolution_unit"] = "km/s"
        data[row + "_rms"] = "0.3"
        data[row + "_rms_unit"] = "mJy/beam"
    for row in spws:
        data.add("spw_rows", row)
        data[row + "_id"] = row
        data[row + "_linked"] = LINE
        data[row + "_bandwidth"] = "1875"
        data[row + "_bandwidth_unit"] = "MHz"
        data[row + "_bandwidth_kind"] = "USABLE"
    for key, value in changes.items():
        data[key] = value
    return data


def test_legacy_form_has_separated_editor_link_and_new_editor_is_nonexecuting(client):
    assert b"/proposed/separated" in client.get("/proposed").data
    page = client.get("/proposed/separated")
    assert page.status_code == 200
    assert b"Requested LINE windows" in page.data
    assert b"Spectral setup evidence" in page.data
    assert b"Run assessment" not in page.data


def test_radius_unit_is_a_legitimate_browser_field_not_a_mixed_contract(client):
    data = form("validate", radius_unit="arcmin")
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert 'name="radius_unit"' in response.text
    assert '<option value="arcmin" selected' in response.text


def test_new_editor_adds_independent_line_and_physical_rows(client):
    original = form("add-spw")
    response = client.post("/proposed/separated", data=original)
    assert response.status_code == 200
    spw_ids = re.findall(r'name="spw_rows" value="(p[0-9a-f]{12})"', response.text)
    line_ids = re.findall(r'name="line_rows" value="(l[0-9a-f]{12})"', response.text)
    assert len(spw_ids) == 1 and line_ids == [LINE]
    assert "LINE requirement 2" not in response.text
    added = form("add-line", spws=(SPW,))
    response = client.post("/proposed/separated", data=added)
    assert response.status_code == 200
    line_ids = re.findall(r'name="line_rows" value="(l[0-9a-f]{12})"', response.text)
    spw_ids = re.findall(r'name="spw_rows" value="(p[0-9a-f]{12})"', response.text)
    assert len(line_ids) == 2 and spw_ids == [SPW]


def test_optional_bandwidth_never_creates_line_requirements_or_rms_requirement(client):
    response = client.post("/proposed/separated", data=form("download", spws=(SPW,)))
    assert response.status_code == 200
    doc = response.get_json()
    assert len(doc["request"]["line_requirements"]) == 1
    assert len(doc["request"]["physical_spw_evidence"]) == 1
    assert doc["request"]["physical_spw_evidence"][0]["linked_line_requirement_id"] == LINE
    assert doc["request"]["physical_spw_evidence"][0]["bandwidth_kind"] == "USABLE"
    assert doc["request"]["physical_spw_inventory_complete"] is False
    assert not {"setup_complete", "sensitivities", "spectral_windows", "line_evaluation_scope"}.intersection(doc["request"])
    validated = validate_proposed_observation(doc["request"], doc["search_options"])
    assert [i.code for i in validated.errors] == ["SEPARATED_INPUT_NOT_EXECUTABLE"]


def test_second_explicit_line_with_missing_rms_blocks_export(client):
    other = "labcdefabcdef"
    data = form("download", rows=(LINE, other))
    del data[other + "_rms"]
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert "request.line_requirements[1].rms" in response.text
    assert "LINE_RMS_REQUIRED" in response.text
    assert response.mimetype == "text/html"


def test_optional_physical_row_without_line_rms_does_not_make_second_line(client):
    data = form("download", spws=(SPW,))
    data[SPW + "_linked"] = ""
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    request = response.get_json()["request"]
    assert len(request["line_requirements"]) == 1
    assert request["physical_spw_evidence"][0].get("linked_line_requirement_id") is None


def test_removing_linked_requirement_requires_explicit_unlink(client):
    response = client.post("/proposed/separated", data=form(f"remove-line:{LINE}", spws=(SPW,)))
    assert response.status_code == 200
    assert "LINKED_LINE_REMOVAL_BLOCKED" in response.text
    assert f'name="line_rows" value="{LINE}"' in response.text


def test_linked_evidence_convenience_is_one_physical_record(client):
    response = client.post("/proposed/separated", data=form(f"add-linked-spw:{LINE}"))
    assert response.status_code == 200
    assert len(re.findall(r'name="spw_rows" value="(p[0-9a-f]{12})"', response.text)) == 1
    assert f'<option value="{LINE}" selected' in response.text


def test_duplicate_or_mixed_contract_editor_fields_rejected(client):
    data = form()
    data.add("line_rows", LINE)
    assert client.post("/proposed/separated", data=data).status_code == 400
    assert client.post("/proposed/separated", data=form(setup_complete="on")).status_code == 400


def test_dangling_link_never_exports_as_valid(client):
    response = client.post("/proposed/separated", data=form("download", spws=(SPW,),
        **{SPW + "_linked": "unknown-line"}))
    assert response.status_code == 200
    assert "DANGLING_REFERENCE" in response.text


def test_ambiguous_spw_links_are_rejected_not_deduplicated(client):
    another = "p123456abcdef"
    data = form("download", spws=(SPW, another))
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    assert "AMBIGUOUS_PHYSICAL_SPW_LINK" in response.text
    assert response.mimetype == "text/html"


def test_mosaic_uses_same_independent_scope_and_shared_redshift(client):
    data = form("download", geometry="MOSAIC", redshift="0.024",
                **{LINE + "_center_kind": "REST"})
    response = client.post("/proposed/separated", data=data)
    assert response.status_code == 200
    doc = response.get_json()
    assert doc["request"]["geometry"] == "MOSAIC"
    assert doc["request"]["position"] is None
    assert doc["request"]["source_redshift"] == "0.024"
    assert doc["request"]["line_requirements"][0]["window_center"]["kind"] == "REST"


def test_new_editor_assess_is_blocked_without_provider(client, monkeypatch):
    from alma_duplicate.ui.runs import BrowserAssessment
    monkeypatch.setattr(BrowserAssessment, "assess", lambda *a, **kw: pytest.fail("source used"))
    monkeypatch.setattr(BrowserAssessment, "assess_mosaic", lambda *a, **kw: pytest.fail("mosaic source used"))
    response = client.post("/proposed/separated", data=form("assess"))
    assert response.status_code == 200
    assert "Assessment is unavailable" in response.text
    assert response.mimetype == "text/html"


def test_manual_form_builder_does_not_double_count_linked_bandwidth():
    values = dict(setup_id="setup-1", geometry="SINGLE_POINTING", **{
        LINE + "_id": LINE, LINE + "_center": "225.1", LINE + "_mode": "FDM",
        LINE + "_resolution": "20", LINE + "_rms": "0.3",
        SPW + "_id": SPW, SPW + "_linked": LINE,
        SPW + "_bandwidth": "1875", SPW + "_bandwidth_kind": "USABLE",
    })
    doc = build_separated_document(values, [LINE], [SPW])
    assert len(doc["request"]["line_requirements"]) == len(doc["request"]["physical_spw_evidence"]) == 1
    assert "bandwidth" not in doc["request"]["line_requirements"][0]
