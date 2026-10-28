"""Archive Mosaic OT form preview is isolated from science and network access."""
import io

import pytest

from alma_duplicate.ui import create_app


OT = (b"RA,Dec,Coordinate Type,Coordinate Units\n"
      b"------------------\n"
      b"201.365,-43.019,Absolute,Degrees\n"
      b"201.366,-43.018,Absolute,Degrees\n"
      b"201.365,-43.019,Absolute,Degrees\n")


@pytest.fixture
def client(monkeypatch):
    import alma_duplicate.assessment as assessment
    import requests

    monkeypatch.setattr(assessment, "assess_observation",
                        lambda *a, **k: pytest.fail("science assessment invoked"))
    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *a, **k: pytest.fail("network invoked"))
    from alma_duplicate.ui.runs import BrowserAssessment
    monkeypatch.setattr(BrowserAssessment, "assess",
                        lambda *a, **k: pytest.fail("browser assessment invoked"))
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None}).test_client()


def upload(client, data=None, raw=OT):
    defaults = dict(target_kind="FIXED", geometry="MOSAIC", mosaic_array="12m",
                    sources="ARCHIVE", action="preview-pointings")
    defaults.update(data or {})
    data = defaults
    data["ot_pointings"] = (io.BytesIO(raw), "pointings.txt")
    return client.post("/proposed", data=data, content_type="multipart/form-data")


def test_mosaic_preview_parses_full_list_with_duplicate_row_identity(client):
    response = upload(client, {"mosaic_fixed_icrs": "on", "mosaic_complete": "on"})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="mosaic-preview-result"' in html
    assert "3 input rows; 1 repeated-coordinate rows" in html
    assert "row-1" in html and "row-3" in html
    assert "All 3 uploaded rows will be checked as fixed ICRS pointings" in html
    assert 'value="preview-pointings"' in html


def test_large_valid_ot_export_previews_first_twenty_only(client):
    rows = [f"{201 + i / 1000},-43,Absolute,Degrees\n".encode()
            for i in range(25)]
    raw = b"RA,Dec,Coordinate Type,Coordinate Units\n--\n" + b"".join(rows)
    html = upload(client, raw=raw).get_data(as_text=True)
    assert "25 input rows" in html
    assert "First 20 of 25 pointings" in html
    assert "row-20" in html and "row-21" not in html


def test_preview_does_not_require_unproven_confirmations(client):
    html = upload(client).get_data(as_text=True)
    assert 'id="mosaic-preview-result"' in html
    assert 'name="mosaic_fixed_icrs"' not in html
    assert 'name="mosaic_complete"' not in html


@pytest.mark.parametrize("bad", [
    b"source,target\n201,-43\n",
    b"RA,Dec,Coordinate Type,Coordinate Units\n--\n201,-43,Offset,Degrees\n",
    b"RA,Dec,Coordinate Type,Coordinate Units\n--\n999,-43,Absolute,Degrees\n",
    b"RA,Dec,Coordinate Type,Coordinate Units\n--\n",
    b"\xff\xfe",
])
def test_invalid_ot_files_do_not_create_a_preview(client, bad):
    response = upload(client, raw=bad)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="mosaic-preview-error"' in html
    assert 'id="mosaic-preview-result"' not in html


def test_oversized_multipart_upload_is_rejected_by_flask(client):
    response = upload(client, raw=OT + b" " * (1024 * 1024))
    assert response.status_code == 413


def test_missing_upload_and_invalid_array_are_errors(client):
    response = client.post("/proposed", data={"action": "preview-pointings",
        "target_kind": "FIXED", "geometry": "MOSAIC", "mosaic_array": "12m"})
    assert 'id="mosaic-preview-error"' in response.get_data(as_text=True)
    response = upload(client, {"mosaic_array": "TP"})
    assert 'id="mosaic-preview-error"' in response.get_data(as_text=True)


@pytest.mark.parametrize("kind,geometry", [
    ("FIXED", "SINGLE_POINTING"), ("MOVING", "MOSAIC"), ("SUN", "MOSAIC")
])
def test_preview_rejects_out_of_scope_observations(client, kind, geometry):
    response = upload(client, {"target_kind": kind, "geometry": geometry})
    assert response.status_code == 400
    assert 'id="mosaic-preview-result"' not in response.get_data(as_text=True)


def test_no_mosaic_preview_controls_on_single_point_form(client):
    html = client.get("/proposed").get_data(as_text=True)
    assert 'id="mosaic-pointings"' not in html
    assert 'value="preview-pointings"' not in html


def test_mosaic_assessment_requires_live_configuration(client):
    response = client.post("/proposed", data={"target_kind": "FIXED",
        "geometry": "MOSAIC", "sources": "ARCHIVE", "action": "assess"})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "requires live Archive configuration" in html


def token_from(response):
    import re
    return re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', response.get_data(as_text=True)).group(1)


def test_upload_survives_edit_and_failed_replacement_then_removal(client):
    token = token_from(upload(client))
    data = dict(target_kind='FIXED', geometry='MOSAIC', action='purpose',
                mosaic_upload_token=token, mosaic_array='7m', mosaic_complete='on',
                intents='CONTINUUM', sources=['ARCHIVE', 'QUEUE'])
    response = client.post('/proposed', data=data)
    html = response.get_data(as_text=True)
    assert '3 input rows' in html
    assert 'proposed array: 7m' in html
    assert 'All 3 uploaded rows will be checked' in html
    assert 'name="sources" value="QUEUE"' not in html
    assert 'id="ra"' not in html
    assert 'centre radius for the supported' not in html
    failed = upload(client, {'mosaic_upload_token': token}, raw=b'invalid')
    assert '3 input rows' in failed.get_data(as_text=True)
    assert token_from(failed) == token
    data['action'] = 'remove-pointings'
    removed = client.post('/proposed', data=data)
    assert 'id="mosaic-preview-result"' not in removed.get_data(as_text=True)
    assert 'name="mosaic_upload_token"' not in removed.get_data(as_text=True)
    data['action'] = 'purpose'
    assert 'expired or is unavailable' in client.post('/proposed', data=data).get_data(as_text=True)


def test_token_is_session_owned_and_replacement_invalidates_old(client):
    token = token_from(upload(client))
    other = client.application.test_client()
    data = dict(target_kind='FIXED', geometry='MOSAIC', action='scope', mosaic_upload_token=token)
    assert '3 input rows' not in other.post('/proposed', data=data).get_data(as_text=True)
    new = token_from(upload(client, {'mosaic_upload_token': token}))
    assert new != token
    assert '3 input rows' not in client.post('/proposed', data=data).get_data(as_text=True)


def test_store_expiry_capacity_and_detached_collection():
    from alma_duplicate.ui.mosaic_uploads import MosaicUploadStore
    now = [0]
    store = MosaicUploadStore(ttl=10, capacity=1, clock=lambda: now[0])
    token = store.put('owner', {'points': [1, 2]})
    copy = store.get('owner', token)
    copy['points'].clear()
    assert store.get('owner', token)['points'] == [1, 2]
    with pytest.raises(ValueError, match='busy'):
        store.put('owner', {})
    now[0] = 10
    assert store.get('owner', token) is None
    store.put('owner', {})
