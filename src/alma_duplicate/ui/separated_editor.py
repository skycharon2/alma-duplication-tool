"""Browser editor for the Step 03b-A separated LINE/SPW wire contract.

No science execution is authorized. This blueprint is deliberately independent
of the legacy /proposed form, its rows, and its working assessment routes.
"""

import re
from uuid import uuid4

from flask import Blueprint, Response, abort, render_template, request

from alma_duplicate.reporting import report_json_text
from alma_duplicate.request_validation import (
    validate_preview_position, validate_proposed_observation,
)
from alma_duplicate.separated_setup_input import SEPARATED_INPUT_CONTRACT

separated_editor = Blueprint("separated_editor", __name__)
MAX_ROWS = 32
LINE_ROW = re.compile(r"l[0-9a-f]{12}\Z")
SPW_ROW = re.compile(r"p[0-9a-f]{12}\Z")
LINE_SUFFIXES = {"_id", "_center", "_center_unit", "_center_kind", "_mode",
                 "_resolution", "_resolution_unit", "_rms", "_rms_unit"}
SPW_SUFFIXES = {"_id", "_linked", "_center", "_center_unit", "_center_kind",
                "_bandwidth", "_bandwidth_unit", "_bandwidth_kind"}
SCALARS = {"action", "setup_id", "target_name", "geometry", "angular", "angular_unit",
           "redshift", "ra", "dec", "ra_format", "dec_format", "radius", "radius_unit",
           "physical_spw_inventory_complete"}
REPEATED = {"line_rows", "spw_rows"}


def _new_row(prefix):
    return prefix + uuid4().hex[:12]


def _read_form(form):
    """No hidden role inference: each repeated list has its own namespace."""
    for key in form:
        if key not in REPEATED and len(form.getlist(key)) != 1:
            raise ValueError("Repeated scalar form field")
    lines = form.getlist("line_rows")
    spws = form.getlist("spw_rows")
    if (len(lines) > MAX_ROWS or len(spws) > MAX_ROWS
            or len(set(lines)) != len(lines) or len(set(spws)) != len(spws)
            or any(not LINE_ROW.fullmatch(row) for row in lines)
            or any(not SPW_ROW.fullmatch(row) for row in spws)):
        raise ValueError("Invalid or repeated LINE/SPW row identities")
    allowed = SCALARS | REPEATED
    allowed.update(row + suffix for row in lines for suffix in LINE_SUFFIXES)
    allowed.update(row + suffix for row in spws for suffix in SPW_SUFFIXES)
    if set(form) - allowed:
        raise ValueError("Unknown or mixed-contract editor field")
    if form.get("physical_spw_inventory_complete", "") not in ("", "on"):
        raise ValueError("Physical SPW completeness must be an explicit checkbox value")
    return form.to_dict(), lines, spws


def _quantity(values, name, default_unit):
    value = values.get(name, "").strip()
    return ({"value": value, "unit": values.get(name + "_unit", default_unit)}
            if value else None)


def _frequency(values, name):
    quantity = _quantity(values, name, "GHz")
    return (quantity | {"kind": values.get(name + "_kind", "SKY"), "frame": "UNKNOWN"}
            if quantity is not None else None)


def build_separated_document(values, line_rows, spw_rows):
    """Faithful export: requirements and physical evidence never share rows."""
    geometry = values.get("geometry", "SINGLE_POINTING")
    observation = {
        "line_input_contract": SEPARATED_INPUT_CONTRACT,
        "target_kind": "FIXED", "geometry": geometry,
        "target_name": values.get("target_name", ""),
        "setup_id": values.get("setup_id", ""), "intents": ["LINE"],
        "line_requirements": [], "physical_spw_evidence": [],
        "physical_spw_inventory_complete": (
            values.get("physical_spw_inventory_complete") == "on"),
    }
    angle = _quantity(values, "angular", "arcsec")
    if angle is not None:
        observation["angular_resolution"] = angle
    redshift = values.get("redshift", "").strip()
    if redshift:
        observation["source_redshift"] = redshift
    if geometry == "SINGLE_POINTING":
        observation["position"] = {
            "ra": values.get("ra", ""), "dec": values.get("dec", ""),
            "ra_format": values.get("ra_format", "DEG"),
            "dec_format": values.get("dec_format", "DEG"), "frame": "ICRS",
        }
    else:
        observation["position"] = None
    for row in line_rows:
        item = {
            "requirement_id": values.get(row + "_id", row),
            "window_center": _frequency(values, row + "_center"),
            "correlator_mode": values.get(row + "_mode", "UNKNOWN"),
            "spectral_resolution": _quantity(values, row + "_resolution", "km/s"),
            "rms": _quantity(values, row + "_rms", "mJy/beam"),
        }
        observation["line_requirements"].append(item)
    for row in spw_rows:
        item = {"spw_id": values.get(row + "_id", row)}
        linked = values.get(row + "_linked", "").strip()
        if linked:
            item["linked_line_requirement_id"] = linked
        center = _frequency(values, row + "_center")
        if center is not None:
            item["center"] = center
        bandwidth = _quantity(values, row + "_bandwidth", "MHz")
        if bandwidth is not None:
            item["bandwidth"] = bandwidth
            item["bandwidth_kind"] = values.get(row + "_bandwidth_kind", "UNKNOWN")
        elif values.get(row + "_bandwidth_kind", "UNKNOWN") != "UNKNOWN":
            # Keep an invalid explicit semantics claim for validation, don't erase it.
            item["bandwidth_kind"] = values[row + "_bandwidth_kind"]
        observation["physical_spw_evidence"].append(item)
    search = {"sources": ["ARCHIVE"], "predicates": []}
    if geometry == "SINGLE_POINTING":
        radius = _quantity(values, "radius", "arcsec")
        if radius is not None:
            search["radius"] = radius
    else:
        search["radius_mode"] = "AUTO"
    return {"request": observation, "search_options": search}


def _additional_form_errors(values):
    """Basic shared target fields must not be silently accepted on export."""
    errors = []
    if values.get("geometry", "SINGLE_POINTING") not in {"SINGLE_POINTING", "MOSAIC"}:
        errors.append({"path": "request.geometry", "code": "INVALID_CHOICE",
                       "message": "Choose Single Pointing or Mosaic."})
    if not values.get("setup_id", "").strip():
        errors.append({"path": "request.setup_id", "code": "REQUIRED_FIELD",
                       "message": "Enter a setup ID."})
    if values.get("geometry", "SINGLE_POINTING") == "MOSAIC":
        if not values.get("target_name", "").strip():
            errors.append({"path": "request.target_name", "code": "REQUIRED_FIELD",
                           "message": "Mosaic requires a target name."})
    else:
        position = {"ra": values.get("ra", ""), "dec": values.get("dec", ""),
                    "ra_format": values.get("ra_format", "DEG"),
                    "dec_format": values.get("dec_format", "DEG"), "frame": "ICRS"}
        _, issues = validate_preview_position(position)
        errors.extend({"path": i.path, "code": i.code, "message": i.message}
                      for i in issues if i.category == "ERROR")
    for key in ("angular", "radius"):
        if key == "radius" and values.get("geometry", "SINGLE_POINTING") == "MOSAIC":
            continue
        unit = values.get(key + "_unit", "arcsec")
        if unit not in ({"arcsec", "mas"} if key == "angular" else {"arcsec", "arcmin", "deg"}):
            errors.append({"path": f"request.{key}", "code": "UNSUPPORTED_UNIT",
                           "message": f"Unsupported {key} unit."})
        raw = values.get(key, "")
        try:
            valid = bool(raw.strip()) and 0 < float(raw) < float("inf")
        except ValueError:
            valid = False
        if not valid:
            errors.append({"path": f"request.{key}", "code": "INVALID_QUANTITY",
                           "message": f"Enter a positive finite {key}."})
    return errors


@separated_editor.route("/proposed/separated", methods=["GET", "POST"])
def edit_separated():
    values = {"setup_id": "setup-1", "geometry": "SINGLE_POINTING",
              "angular_unit": "arcsec", "radius_unit": "arcsec"}
    line_rows = [_new_row("l")]
    spw_rows = []
    errors = []
    notice = None
    if request.method == "POST":
        try:
            values, line_rows, spw_rows = _read_form(request.form)
        except ValueError as exc:
            abort(400, description=str(exc))
        action = values.get("action", "validate")
        if action == "add-line":
            if len(line_rows) >= MAX_ROWS:
                abort(400)
            line_rows.append(_new_row("l"))
        elif action == "add-spw":
            if len(spw_rows) >= MAX_ROWS:
                abort(400)
            spw_rows.append(_new_row("p"))
        elif action.startswith("add-linked-spw:"):
            line_row = action.partition(":")[2]
            if line_row not in line_rows or len(spw_rows) >= MAX_ROWS:
                abort(400)
            identifier = values.get(line_row + "_id", line_row)
            if any(values.get(spw + "_linked") == identifier for spw in spw_rows):
                errors.append({"path": "request.physical_spw_evidence",
                               "code": "LINK_ALREADY_PRESENT",
                               "message": "This LINE requirement already has linked SPW evidence."})
            else:
                new_spw = _new_row("p")
                spw_rows.append(new_spw)
                values[new_spw + "_linked"] = identifier
        elif action.startswith("remove-line:"):
            row = action.partition(":")[2]
            if row not in line_rows:
                abort(400)
            identifier = values.get(row + "_id", row)
            if any(values.get(spw + "_linked") == identifier for spw in spw_rows):
                errors.append({"path": "request.physical_spw_evidence",
                               "code": "LINKED_LINE_REMOVAL_BLOCKED",
                               "message": "Unlink the physical SPW before removing this LINE requirement."})
            else:
                line_rows.remove(row)
        elif action.startswith("remove-spw:"):
            row = action.partition(":")[2]
            if row not in spw_rows:
                abort(400)
            spw_rows.remove(row)
        elif action in {"validate", "download", "assess"}:
            doc = build_separated_document(values, line_rows, spw_rows)
            validation = validate_proposed_observation(doc["request"], doc["search_options"])
            errors.extend({"path": i.path, "code": i.code, "message": i.message}
                          for i in validation.errors if i.code != "SEPARATED_INPUT_NOT_EXECUTABLE")
            errors.extend(_additional_form_errors(values))
            if action == "assess":
                notice = "Assessment is unavailable for this separated contract until the versioned evaluator is approved."
            elif not errors and action == "download":
                return Response(report_json_text(doc), mimetype="application/json",
                                headers={"Content-Disposition": 'attachment; filename="separated-proposed-request.json"'})
            elif not errors:
                notice = "Record structure validated. Formal assessment remains unavailable."
        else:
            abort(400)
    line_ids = [(values.get(row + "_id", row), i + 1) for i, row in enumerate(line_rows)]
    return render_template("proposed_separated.html", values=values,
                           line_rows=line_rows, spw_rows=spw_rows,
                           line_ids=line_ids, errors=errors, notice=notice,
                           max_rows=MAX_ROWS)
