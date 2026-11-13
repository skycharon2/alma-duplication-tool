"""Offline batch preflight using the standalone form's validation rules."""
from alma_duplicate.batch_request import build_batch_requests
from alma_duplicate.ui.proposed import build_document, validate_document_for_browser


def prepare_batch_form(values, rows, source_bytes, *, format='csv', require_line_complete=False):
    """Build all targets before validation; retain every child's diagnostics.

    Does not execute, split purposes, store reports or discard invalid children.
    A source list's z replaces all shared/local form redshifts in child requests.
    """
    shared, _ = build_document(values, rows)
    batch = build_batch_requests(shared, source_bytes, format=format)
    for child in batch['sources']:
        result, _ = validate_document_for_browser(
            child['document'], values, rows, require_line_complete=require_line_complete)
        child['validation'] = result
    batch['is_valid'] = all(child['validation'].is_valid for child in batch['sources'])
    batch['can_search'] = all(child['validation'].can_search for child in batch['sources'])
    return batch
