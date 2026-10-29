"""Mosaic OT upload form state, independent of Single Pointing science.

The session-owned temporary upload store and parsing/validation rules are
unchanged. Upload actions never assess candidates or query Archive/Queue.
"""

from alma_duplicate.ui.proposed import preview_mosaic_ot


def restore_mosaic_upload(values, store, owner):
    """Get the retained collection, dropping expired/foreign form tokens."""
    token = values.get("mosaic_upload_token", "")
    if not token:
        return token, None, None
    preview = store.get(owner, token)
    if preview is None:
        values.pop("mosaic_upload_token", None)
        return token, None, "The OT upload expired or is unavailable. Import the file again."
    return token, preview, None


def replace_mosaic_upload(values, store, owner, old_token, files):
    """Validate and store a new collection before invalidating the old token.

    A parse error or full upload store must leave the old input untouched.
    """
    if len(files) != 1:
        raise ValueError("Select one OT pointings file")
    replacement = preview_mosaic_ot(files[0], values)
    new_token = store.put(owner, replacement)
    store.remove(owner, old_token)
    values["mosaic_upload_token"] = new_token
    return replacement


def remove_mosaic_upload(values, store, owner, token):
    """Remove only the caller's retained upload and its confirmations."""
    store.remove(owner, token)
    values.pop("mosaic_upload_token", None)
    values.pop("mosaic_complete", None)
    values.pop("mosaic_fixed_icrs", None)
