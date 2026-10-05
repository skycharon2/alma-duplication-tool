"""Browser wire-input adapter; scientific validation belongs to the backend."""

import re
from uuid import uuid4

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.domain.proposed_observation import CONTINUUM_SETUP_DECLARATION

MAX_WINDOWS = 32
ROW = re.compile(r"w[0-9a-f]{12}\Z")


def new_row():
    return "w" + uuid4().hex[:12]


def initial_form():
    return {"setup_id": "setup-1", "radius_mode": "AUTO"}, []


def assessment_supported(values):
    """Browser execution scope; backend scientific readiness remains separate."""
    return (values.get("target_kind", "FIXED") == "FIXED"
            and values.get("geometry", "SINGLE_POINTING") == "SINGLE_POINTING")


def read_form(form):
    """Preserve raw strings; reject ambiguous wire shape before field mapping."""
    repeated = {"rows", "intents", "sources", "aggregate_windows"}
    for key in form:
        if key not in repeated and len(form.getlist(key)) != 1:
            raise ValueError("Repeated scalar form field")
    rows = form.getlist("rows")
    if len(rows) > MAX_WINDOWS or len(set(rows)) != len(rows):
        raise ValueError("Invalid window row list (maximum 32)")
    if any(not ROW.fullmatch(row) for row in rows):
        raise ValueError("Invalid window row identity")
    values = form.to_dict()
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
    # Non-fixed targets need not supply coordinates. Keep any supplied values
    # for provenance/validation, but do not invent an empty position.
    if request["target_kind"] != "FIXED" and not any(values.get(k, "").strip() for k in ("ra", "dec")):
        request["position"] = None
    redshift = raw("redshift", "request.source_redshift")
    declaration = raw("continuum_setup_declaration", "request.continuum_setup_declaration")
    if declaration:
        request["continuum_setup_declaration"] = CONTINUUM_SETUP_DECLARATION if declaration == "on" else declaration
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
    return {"request": request, "search_options": search}, bindings


def validate_form(values, rows):
    document, bindings = build_document(values, rows)
    result = validate_proposed_observation(document["request"], document["search_options"])
    issues = []
    for issue in result.issues:
        candidates = [path for path in bindings if issue.path == path or
                      issue.path.startswith(path + ".") or issue.path.startswith(path + "[")]
        field = bindings[max(candidates, key=len)] if candidates else "validation"
        issues.append({"issue": issue, "field": field})
    return document, result, issues
