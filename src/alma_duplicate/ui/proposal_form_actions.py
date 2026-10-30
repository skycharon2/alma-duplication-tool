"""Shared browser form state and non-scientific input editing actions.

Single Pointing and Mosaic controllers own their validation and execution
paths. This module only edits submitted fields; it never queries a source.
"""

from dataclasses import dataclass, field

from flask import abort

from alma_duplicate.ui.proposed import MAX_WINDOWS, new_row
from alma_duplicate.ui.workflow_policy import should_enable_mosaic_v2_on_scope_change


@dataclass
class ProposalFormState:
    values: dict
    rows: list
    result: object = None
    issues: list = field(default_factory=list)
    document: dict | None = None
    pending_removal: str | None = None
    edit_notice: str | None = None
    added_row: str | None = None
    purpose_updated: bool = False
    scope_updated: bool = False
    execution_error: str | None = None
    mosaic_preview: dict | None = None
    mosaic_preview_error: str | None = None
    mosaic_ready: bool = False
    owner: str = ""
    upload_token: str = ""


def apply_common_edit(state: ProposalFormState, action: str) -> bool:
    """Edit shared scientific *inputs* without running validation or assessment.

    Return False for unknown/workflow-specific actions so the route rejects them.
    """
    values, rows = state.values, state.rows
    if action == "scope":
        # Only blank Mosaic forms are upgraded; retain Single Pointing inputs.
        if should_enable_mosaic_v2_on_scope_change(values, rows):
            values["normal_form_version"] = "2"
        state.scope_updated = True
        state.edit_notice = "Observation type updated. Entered values are retained; validate again."
    elif action == "purpose":
        state.purpose_updated = True
        if "LINE" in values.get("intents", []) and not rows:
            state.added_row = new_row()
            rows.append(state.added_row)
        state.edit_notice = "Requirement sections updated. Entered values are retained; validate again."
    elif action == "add-spw":
        spws = values.setdefault("spw_rows", [])
        if len(spws) >= MAX_WINDOWS:
            abort(400, description="Maximum 32 physical SPW records")
        spws.append(new_row())
        state.edit_notice = "Physical SPW evidence added. LINE requirements are unchanged."
    elif action.startswith("remove-spw:"):
        row = action.split(":", 1)[1]
        if row not in values.get("spw_rows", []):
            abort(400)
        values["spw_rows"].remove(row)
        state.edit_notice = "Physical SPW evidence removed. LINE requirements are unchanged."
    elif action == "add":
        from alma_duplicate.ui.normal_line_input import uses_separated_input
        if ("LINE" in values.get("intents", []) and rows
                and uses_separated_input(values)):
            state.edit_notice = ("One LINE configuration per V2 browser assessment. "
                                 "Start a new assessment for another independent setup.")
        else:
            if len(rows) >= MAX_WINDOWS:
                abort(400, description="Maximum 32 windows in this form")
            state.added_row = new_row()
            rows.append(state.added_row)
            state.edit_notice = "Window added. Validate input to update the diagnostics."
    elif action.startswith(("remove:", "confirm-remove:")):
        row = action.split(":", 1)[1]
        if row not in rows:
            abort(400)
        if action.startswith("confirm-remove:"):
            rows.remove(row)
            state.edit_notice = "Window removed with its LINE inputs. Review any retained continuum references and validate again."
        else:
            state.pending_removal = row
    elif action == "cancel-remove":
        state.edit_notice = "Window retained. Validate input to update the diagnostics."
    else:
        return False
    return True
