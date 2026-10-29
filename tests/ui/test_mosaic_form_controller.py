"""Mosaic OT upload controller: retained token/owner isolation and failure atomicity."""

import io

import pytest
from werkzeug.datastructures import FileStorage

from alma_duplicate.ui.mosaic_form import (
    remove_mosaic_upload, replace_mosaic_upload, restore_mosaic_upload,
)
from alma_duplicate.ui.mosaic_uploads import MosaicUploadStore
from tests.ui.test_mosaic_ot_preview import OT


def values():
    return {"target_kind": "FIXED", "geometry": "MOSAIC", "mosaic_array": "12m"}


def file(raw=OT):
    return FileStorage(stream=io.BytesIO(raw), filename="pointings.txt")


def test_replace_and_restore_are_session_owned():
    store = MosaicUploadStore()
    form = values()
    preview = replace_mosaic_upload(form, store, "owner-a", "", [file()])
    token = form["mosaic_upload_token"]
    assert preview["row_count"] == 3
    assert restore_mosaic_upload(form, store, "owner-a")[1]["row_count"] == 3
    foreign = values() | {"mosaic_upload_token": token}
    _, result, error = restore_mosaic_upload(foreign, store, "owner-b")
    assert result is None and "expired or is unavailable" in error
    assert "mosaic_upload_token" not in foreign
    assert store.get("owner-a", token) is not None


def test_failed_replace_does_not_erase_previous_upload():
    store = MosaicUploadStore()
    form = values()
    replace_mosaic_upload(form, store, "owner-a", "", [file()])
    token = form["mosaic_upload_token"]
    with pytest.raises(ValueError):
        replace_mosaic_upload(form, store, "owner-a", token, [file(b"invalid")])
    assert form["mosaic_upload_token"] == token
    assert store.get("owner-a", token) is not None
    with pytest.raises(ValueError, match="Select one OT pointings file"):
        replace_mosaic_upload(form, store, "owner-a", token, [])
    assert store.get("owner-a", token) is not None


def test_removal_clears_only_mosaic_upload_controls():
    store = MosaicUploadStore()
    form = values() | {"mosaic_complete": "on", "mosaic_fixed_icrs": "on",
                      "aggregate": "0.01"}
    replace_mosaic_upload(form, store, "owner-a", "", [file()])
    token = form["mosaic_upload_token"]
    remove_mosaic_upload(form, store, "owner-a", token)
    assert store.get("owner-a", token) is None
    assert "mosaic_upload_token" not in form
    assert "mosaic_complete" not in form
    assert "mosaic_fixed_icrs" not in form
    assert form["aggregate"] == "0.01"
