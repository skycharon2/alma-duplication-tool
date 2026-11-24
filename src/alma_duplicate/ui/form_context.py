"""Shared presentation context for standalone and batch scientific forms."""
from alma_duplicate.auto_retrieval import automatic_scope
from alma_duplicate.ui.proposed import assessment_supported, contributing_windows
from alma_duplicate.ui.managed_queue import managed_queue_status
from alma_duplicate.ui.archive_status import archive_configuration_status


def form_context(state, configured):
    values, rows = state.values, state.rows
    if state.mosaic_preview:
        state.mosaic_preview["array"] = values.get("mosaic_array", "12m")
        state.mosaic_preview["fixed_icrs_confirmed"] = values.get("mosaic_fixed_icrs") == "on"
        state.mosaic_preview["complete_confirmed"] = values.get("mosaic_complete") == "on"
    for row in rows + values.get("spw_rows", []):
        values.setdefault(row + "_id", row)
    # Carry the shared target value into new local controls without replacing
    # explicit per-frequency values, including deliberately cleared inputs.
    if values.get("redshift", "").strip():
        values.setdefault("continuum_redshift", values["redshift"])
        for row in rows:
            values.setdefault(row + "_redshift", values["redshift"])
    selected = contributing_windows(values)
    from alma_duplicate.ui.normal_line_input import uses_separated_input
    physical_rows = values.get('spw_rows', []) if uses_separated_input(values) else rows
    known_ids = {values[row + "_id"] for row in physical_rows}
    stale_ids = list(dict.fromkeys(value for value in selected if value not in known_ids))
    return dict(
        values=values, rows=rows,
        result=state.result, issues=state.issues, document=state.document,
        selected_windows=selected, stale_ids=stale_ids,
        pending_removal=state.pending_removal, edit_notice=state.edit_notice,
        original_assessment_url=state.original_assessment_url,
        added_row=state.added_row,
        purpose_updated=state.purpose_updated,
        scope_updated=state.scope_updated, assessment_supported=assessment_supported(values),
        mosaic_preview=state.mosaic_preview, mosaic_preview_error=state.mosaic_preview_error,
        mosaic_ready=state.mosaic_ready,
        configured=configured, execution_error=state.execution_error, auto_scope=automatic_scope(),
        archive_status=archive_configuration_status(configured.archive_kind),
        queue_status=(managed_queue_status(configured.managed_queue_root)
                      if configured.managed_queue_root else None))
