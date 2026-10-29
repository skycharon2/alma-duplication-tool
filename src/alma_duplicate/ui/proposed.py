"""Browser wire-input adapter; scientific validation belongs to the backend."""

import csv
import re
from uuid import uuid4

from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.domain.proposed_observation import CONTINUUM_SETUP_DECLARATION

MAX_WINDOWS = 32
ROW = re.compile(r"w[0-9a-f]{12}\Z")


def new_row():
    return "w" + uuid4().hex[:12]


def initial_form():
    # Single Pointing defaults to its established Archive + Queue (legacy) contract.
    # Explicit V2 inputs and the Mosaic editor remain available independently.
    return {"setup_id": "setup-1", "radius_mode": "AUTO",
            "sources": ["ARCHIVE", "QUEUE"]}, []


def assessment_supported(values):
    """Browser execution scope; backend scientific readiness remains separate."""
    return (values.get("target_kind", "FIXED") == "FIXED"
            and values.get("geometry", "SINGLE_POINTING") in {"SINGLE_POINTING", "MOSAIC"})


def preview_mosaic_ot(upload, values):
    """Preview one native OT export; never enable science or retain its raw bytes."""
    if values.get("target_kind") != "FIXED" or values.get("geometry") != "MOSAIC":
        raise ValueError("OT preview is for fixed-target Mosaic observations only")
    array = values.get("mosaic_array", "12m")
    if array not in {"7m", "12m"}:
        raise ValueError("Select the proposed 7m or 12m array")
    for name in ("mosaic_fixed_icrs", "mosaic_complete"):
        if values.get(name, "") not in ("", "on"):
            raise ValueError("Invalid Mosaic confirmation value")
    if upload is None or not upload.filename:
        raise ValueError("Choose an OT pointings file to preview")
    # A bounded read also protects direct callers outside Flask's 1 MiB request cap.
    from alma_duplicate.parsers.ot_pointings import MAX_BYTES
    try:
        parsed = parse_ot_pointings(upload.stream.read(MAX_BYTES + 1))
    except csv.Error as exc:
        raise ValueError("Malformed OT pointings CSV") from exc
    return {
        "array": array,
        "row_count": parsed["row_count"],
        "coordinate_units": parsed["coordinate_units"],
        "input_sha256": parsed["input_sha256"],
        "duplicate_count": len(parsed["duplicate_coordinates"]),
        "points": [{"id": row["id"], "line_number": row["line_number"],
                    "ra_deg": row["ra_deg"], "dec_deg": row["dec_deg"]}
                   for row in parsed["points"][:20]],
        "preview_limit": 20,
        "collection": parsed,
        "filename": upload.filename.replace("\\", "/").split("/")[-1][:200],
        "fixed_icrs_confirmed": values.get("mosaic_fixed_icrs") == "on",
        "complete_confirmed": values.get("mosaic_complete") == "on",
    }


def read_form(form):
    """Preserve raw strings; reject ambiguous wire shape before field mapping."""
    repeated = {"rows", "intents", "sources", "aggregate_windows", "spw_rows"}
    for key in form:
        if key not in repeated and len(form.getlist(key)) != 1:
            raise ValueError("Repeated scalar form field")
    rows = form.getlist("rows")
    if len(rows) > MAX_WINDOWS or len(set(rows)) != len(rows):
        raise ValueError("Invalid window row list (maximum 32)")
    if any(not ROW.fullmatch(row) for row in rows):
        raise ValueError("Invalid window row identity")
    spws = form.getlist("spw_rows")
    if (len(spws) > MAX_WINDOWS or len(set(spws)) != len(spws)
            or any(not ROW.fullmatch(row) for row in spws) or set(spws) & set(rows)):
        raise ValueError("Invalid physical SPW row identities")
    values = form.to_dict()
    values["spw_rows"] = spws
    values["intents"] = form.getlist("intents")
    values["sources"] = form.getlist("sources")
    values["aggregate_windows"] = [value for item in form.getlist("aggregate_windows") for value in item.split()]
    return values, rows


def contributing_windows(values):
    """Accept checkbox selections and the previous form's text representation."""
    selected = values.get("aggregate_windows", [])
    return selected.split() if isinstance(selected, str) else selected


def build_document(values, rows):
    """Construct existing request schema without unit conversion or defaults for science."""
    bindings = {}

    def raw(name, path):
        bindings[path] = name
        return values.get(name, "")

    def quantity(name, path, default_unit):
        value = raw(name, path)
        if not value.strip():
            return None
        return {"value": value, "unit": values.get(name + "_unit", default_unit)}

    def frequency(name, path, kind):
        q = quantity(name, path, "GHz")
        if q is None:
            return None
        return q | {"kind": values.get(name + "_kind", kind), "frame": "UNKNOWN"}

    setup = raw("setup_id", "request.setup_id")
    request = {
        "target_kind": raw("target_kind", "request.target_kind") if "target_kind" in values else "FIXED",
        "geometry": raw("geometry", "request.geometry") if "geometry" in values else "SINGLE_POINTING",
        "target_name": raw("target_name", "request.target_name"),
        "position": {
            "ra": raw("ra", "request.position.ra"),
            "dec": raw("dec", "request.position.dec"),
            "ra_format": values.get("ra_format", "DEG"),
            "dec_format": values.get("dec_format", "DEG"), "frame": "ICRS",
        },
        "setup_id": setup,
        "setup_complete": values.get("setup_complete") == "on",
        "intents": values.get("intents", []),
        "angular_resolution": quantity("angular", "request.angular_resolution", "arcsec"),
        "representative_frequency": frequency("representative", "request.representative_frequency", "SKY"),
        "spectral_windows": [], "sensitivities": [],
    }
    # Preserve an explicitly supplied wire scope, including rejected values.
    # Normal browser forms omit this field and keep legacy report bytes stable.
    if "line_evaluation_scope" in values:
        request["line_evaluation_scope"] = values["line_evaluation_scope"]
        bindings["request.line_evaluation_scope"] = "line_evaluation_scope"
    # Non-fixed targets need not supply coordinates. Keep any supplied values
    # for provenance/validation, but do not invent an empty position.
    if (request["target_kind"] == "FIXED" and request["geometry"] == "MOSAIC") or (
            request["target_kind"] != "FIXED" and not any(values.get(k, "").strip() for k in ("ra", "dec"))):
        request["position"] = None
    redshift = raw("redshift", "request.source_redshift")
    declaration = raw("continuum_setup_declaration", "request.continuum_setup_declaration")
    # The browser only serializes an explicit confirmation. The purpose is
    # independent of the bandwidth evidence, and a raw API-style form POST
    # must retain the existing non-declaration qualification path.
    if declaration:
        request["continuum_setup_declaration"] = (
            CONTINUUM_SETUP_DECLARATION if declaration == "on" else declaration
        )
    if redshift.strip():
        request["source_redshift"] = redshift
    bindings.update({"request.intents": "intents", "request.setup_complete": "setup_complete",
                     "request.position": "position", "request.spectral_windows": "windows",
                     "request.sensitivities": "sensitivities", "search_options.sources": "sources"})
    aggregate = quantity("aggregate", "request.sensitivities", "mJy/beam")
    if aggregate is not None:
        i = len(request["sensitivities"])
        bindings[f"request.sensitivities[{i}]"] = "aggregate"
        bindings[f"request.sensitivities[{i}].rms"] = "aggregate"
        bindings[f"request.sensitivities[{i}].window_ids"] = "aggregate_windows"
        request["sensitivities"].append({
            "sensitivity_id": "aggregate", "purpose": "CONTINUUM", "scope": "SETUP",
            "setup_id": setup, "basis": "AGGREGATE", "aggregate_path": "DIRECT_DECLARATION",
            "rms": aggregate,
            "window_ids": contributing_windows(values),
        })
    for i, row in enumerate(rows):
        path = f"request.spectral_windows[{i}]"
        bindings[path] = row
        window_id = raw(row + "_id", path + ".window_id")
        window = {"window_id": window_id,
                  "center": frequency(row + "_center", path + ".center", "SKY"),
                  "correlator_mode": values.get(row + "_mode", "UNKNOWN")}
        bandwidth = quantity(row + "_bandwidth", path + ".bandwidth", "MHz")
        if bandwidth is not None:
            window.update(representation="CENTER_BANDWIDTH", bandwidth=bandwidth,
                          bandwidth_kind=values.get(row + "_bandwidth_kind", "UNKNOWN"))
        request["spectral_windows"].append(window)
        rms = values.get(row + "_rms", "")
        resolution = values.get(row + "_resolution", "")
        if rms.strip() or resolution.strip():
            sp = f"request.sensitivities[{len(request['sensitivities'])}]"
            bindings[sp] = row
            request["sensitivities"].append({
                "sensitivity_id": "line-" + row, "purpose": "LINE", "scope": "WINDOW",
                "window_ids": [window_id], "basis": "SMOOTHED",
                "rms": quantity(row + "_rms", sp + ".rms", "mJy/beam"),
                "smoothing_resolution": quantity(row + "_resolution", sp + ".smoothing_resolution", "km/s"),
            })
    limit = raw("result_limit", "search_options.result_limit")
    search = {"radius": quantity("radius", "search_options.radius", "arcsec"),
              "sources": values.get("sources", []), "predicates": []}
    mode = values.get('radius_mode', 'EXPLICIT' if 'radius' in values else 'AUTO')
    if mode != 'EXPLICIT':
        search['radius_mode'] = mode
        # Retain a supplied conflicting radius for backend diagnosis, never ignore it.
        if search['radius'] is None:
            search.pop('radius')
    bindings['search_options.radius_mode'] = 'search'
    if limit.strip():
        # The backend expects an integer here, unlike quantity values.
        search["result_limit"] = int(limit) if re.fullmatch(r"[0-9]{1,9}", limit) else limit
    if request["target_kind"] == "FIXED" and request["geometry"] == "MOSAIC":
        search = {"sources": ["ARCHIVE"], "predicates": [], "radius_mode": "AUTO"}
    document = {"request": request, "search_options": search}
    if values.get("normal_line_records") == "1":
        from alma_duplicate.ui.normal_line_input import enabled, convert
        if enabled(values):
            document = convert(document, values, rows, bindings)
        else:
            request["line_input_contract"] = "UNSUPPORTED_BROWSER_LINE_SCOPE"
    return document, bindings


def _continuum_inventory_errors(request):
    """Reject uncorroborated *browser* completeness claims, not API requests.

    The shared validator and CONT-SETUP science still retain conflicting raw
    declarations as inspectable scientific uncertainty for CLI callers.
    """
    if (request is None or request.target_kind == "SUN"
            or "CONTINUUM" not in request.intents
            or request.continuum_setup_declaration is None
            or request.setup_complete is not True):
        return ()
    from alma_duplicate.rules.continuum_setup import (
        MIN_QUALIFYING_WINDOWS, QUALIFIED, NOT_QUALIFIED, qualify_window,
    )
    from alma_duplicate.domain.proposed_observation import RequestIssue

    statuses = [qualify_window(window)[0] for window in request.spectral_windows]
    qualified = sum(status == QUALIFIED for status in statuses)
    possible = sum(status != NOT_QUALIFIED for status in statuses)
    if possible < MIN_QUALIFYING_WINDOWS:
        return (RequestIssue(
            "ERROR", "CONTINUUM_SETUP_DECLARATION_CONFLICT",
            "request.continuum_setup_declaration",
            "The declared complete SPW list cannot contain two distinct windows "
            "with usable bandwidth strictly greater than 1.8 GHz. Correct the "
            "list or its completeness claim.", None, "PROPOSED"),)
    if qualified < MIN_QUALIFYING_WINDOWS:
        return (RequestIssue(
            "ERROR", "INCOMPLETE_CONTINUUM_WINDOW_EVIDENCE",
            "request.spectral_windows",
            "The claimed complete SPW list does not verify two distinct usable "
            "bandwidths greater than 1.8 GHz. Supply sufficient usable-width "
            "evidence or withdraw the completeness claim.", None, "PROPOSED"),)
    return ()


def _line_run_requirements(request, rows):
    """Browser Run-only completeness gate; never changes shared science verdicts.

    Each submitted window is a LINE requirement while the LINE purpose is
    selected. Physical SPW bandwidth and setup_complete are deliberately ignored.
    """
    from alma_duplicate.domain.proposed_observation import RequestIssue
    from alma_duplicate.proposed_line import prepare_line_window

    if request is None or "LINE" not in request.intents or request.target_kind != "FIXED":
        return ()

    errors = []

    def add(field, path, code, message):
        errors.append((field, RequestIssue(
            "ERROR", code, path, message, "LINE", "PROPOSED",
        )))

    if not request.spectral_windows:
        add("line_requirements", "request.spectral_windows", "LINE_WINDOW_REQUIRED",
            "Add at least one requested LINE window before running an assessment.")
        return tuple(errors)

    for index, window in enumerate(request.spectral_windows):
        row = rows[index]
        path = f"request.spectral_windows[{index}]"
        prepared = prepare_line_window(window, request.sensitivities, request.source_redshift)
        if window.center is None or prepared.sky_frequency_ghz_exact is None:
            if window.center is not None and window.center.kind == "REST" and request.source_redshift is None:
                add("redshift", "request.source_redshift", "LINE_REST_REDSHIFT_REQUIRED",
                    f"Requested LINE window {index + 1} uses REST frequency; enter a source redshift to convert it to SKY.")
            else:
                add(row + "_center", path + ".center", "LINE_SKY_FREQUENCY_REQUIRED",
                    f"Requested LINE window {index + 1} needs a valid SKY frequency or a convertible REST frequency.")
        if window.correlator_mode == "UNKNOWN":
            add(row + "_mode", path + ".correlator_mode", "LINE_MODE_REQUIRED",
                f"Select an explicit correlator mode for requested LINE window {index + 1} (FDM or TDM).")
        if prepared.planned_resolution_kms_exact is None:
            add(row + "_resolution", path + ".spectral_resolution", "LINE_RESOLUTION_REQUIRED",
                f"Enter a usable planned spectral resolution for requested LINE window {index + 1}; conflicting declarations must be resolved.")
        matches = [s for s in request.sensitivities if s.purpose == "LINE"
                   and s.scope == "WINDOW" and s.window_ids == (window.window_id,)]
        if len(matches) != 1 or matches[0].rms is None or matches[0].basis not in {"SMOOTHED", "NATIVE_CHANNEL"}:
            add(row + "_rms", path + ".sensitivities", "LINE_RMS_REQUIRED",
                f"Enter one valid window-specific LINE RMS for requested LINE window {index + 1}.")
    return tuple(errors)


def validate_form(values, rows, *, require_line_complete=False):
    document, bindings = build_document(values, rows)
    separated = "line_input_contract" in document["request"]
    if separated:
        from alma_duplicate.ui.normal_line_input import validate
        result = validate(document)
    else:
        result = validate_proposed_observation(document["request"], document["search_options"])
    line_errors = ()
    if result.is_valid:
        from dataclasses import replace
        from alma_duplicate.domain.proposed_observation import SearchReadiness
        if require_line_complete and not separated:
            line_errors = _line_run_requirements(result.request, rows)
        result = replace(
            result,
            issues=result.issues + (() if separated else _continuum_inventory_errors(result.request)) +
                   tuple(issue for _, issue in line_errors),
            search_readiness=(SearchReadiness.BLOCKED if line_errors else result.search_readiness),
        )
    exact_fields = {issue.path: field for field, issue in line_errors}
    issues = []
    for issue in result.issues:
        candidates = [path for path in bindings if issue.path == path or
                      issue.path.startswith(path + ".") or issue.path.startswith(path + "[")]
        field = exact_fields.get(issue.path) or (bindings[max(candidates, key=len)] if candidates else "validation")
        issues.append({"issue": issue, "field": field})
    return document, result, issues


def bind_mosaic_input(values, preview):
    """Bind the complete owned upload to the current form, without a centre proxy."""
    from copy import deepcopy
    from alma_duplicate.mosaic_candidate_discovery import plan_discovery
    if preview is None:
        raise ValueError("Import an OT pointings file before running Mosaic assessment.")
    name = values.get("target_name", "").strip()
    array = values.get("mosaic_array", "")
    if not name or array not in {"7m", "12m"}:
        raise ValueError("Enter a target name and select the proposed 7m or 12m array.")
    proposed = deepcopy(preview["collection"])
    proposed.update(source_name=name, array=array,
                    declaration_basis="BROWSER_OT_UPLOAD_FIXED_ICRS_COMPLETE_LIST",
                    binding_basis="USER_SUPPLIED_NOT_ENCODED_IN_OT_FILE",
                    frame_basis="USER_CONFIRMED_FIXED_ICRS",
                    completeness="USER_CONFIRMED_COMPLETE")
    plan_discovery(proposed, margin_arcsec=1.0)
    return proposed
