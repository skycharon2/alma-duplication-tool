"""One offline entry point for request parsing, validation and readiness.

No ingestion adapters, candidate evidence, network calls or policy verdicts.
The wire input is a string-keyed mapping with JSON-like scalar/list values.
"""

from collections.abc import Mapping
import math
import re
from types import MappingProxyType

from alma_duplicate.domain.proposed_observation import (
    CandidatePredicate,
    ProposedObservationRequest,
    ProposedSensitivity,
    ProposedWindow,
    RequestFrequency,
    RequestInterval,
    RequestIssue,
    RequestPosition,
    RequestQuantity,
    RequestValidationResult,
    SearchOptions,
    SearchReadiness,
)

_UNITS = {
    "frequency": ("GHz", {"Hz": 1e-9, "kHz": 1e-6, "MHz": 1e-3, "GHz": 1.0}),
    "width": ("MHz", {"Hz": 1e-6, "kHz": 1e-3, "MHz": 1.0, "GHz": 1e3}),
    "angle": ("arcsec", {"mas": 1e-3, "arcsec": 1.0}),
    "radius": ("deg", {"arcsec": 1 / 3600, "arcmin": 1 / 60, "deg": 1.0}),
    "rms": ("mJy/beam", {"Jy/beam": 1e3, "mJy/beam": 1.0}),
    "velocity": ("km/s", {"km/s": 1.0, "m/s": 1e-3}),
}
_FRAMES = {"TOPOCENTRIC", "BARYCENTRIC", "LSRK", "LSRD", "HELIOCENTRIC", "UNKNOWN"}
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


class _Validator:
    def __init__(self):
        self.issues = []

    def issue(self, category, code, path, message, rule=None):
        self.issues.append(
            RequestIssue(
                category,
                code,
                path,
                message,
                rule,
                "METHOD" if category == "CAPABILITY" else "PROPOSED",
            )
        )

    def error(self, code, path, message):
        self.issue("ERROR", code, path, message)

    def missing(self, path, message, rule=None):
        self.issue("MISSING", "MISSING_EVIDENCE", path, message, rule)

    def capability(self, path, message, rule=None, code="METHOD_NOT_IMPLEMENTED"):
        self.issue("CAPABILITY", code, path, message, rule)

    def snapshot(self, value, path, ancestors=None):
        """Detach nested input; reject unsupported cells without retaining aliases."""
        ancestors = set() if ancestors is None else ancestors
        if value is None or type(value) in (str, bool, int, float):
            return value
        if isinstance(value, Mapping) or type(value) in (list, tuple):
            if id(value) in ancestors:
                self.error("CYCLIC_INPUT", path, "Input must be acyclic.")
                return "<cyclic input>"
            ancestors.add(id(value))
            try:
                if isinstance(value, Mapping):
                    result = {}
                    for key, item in value.items():
                        if type(key) is not str:
                            self.error(
                                "INVALID_KEY", path, "Object keys must be strings."
                            )
                            continue
                        result[key] = self.snapshot(item, f"{path}.{key}", ancestors)
                    return MappingProxyType(result)
                return tuple(
                    self.snapshot(item, f"{path}[{i}]", ancestors)
                    for i, item in enumerate(value)
                )
            finally:
                ancestors.remove(id(value))
        self.error("UNSUPPORTED_TYPE", path, "Use plain scalar, object or list input.")
        return f"<unsupported {type(value).__name__}>"

    def obj(self, value, path, allowed):
        if not isinstance(value, Mapping):
            self.error("INVALID_SHAPE", path, "Expected an object.")
            return {}
        for name in value:
            if name not in allowed:
                self.error("UNKNOWN_FIELD", f"{path}.{name}", "Unknown input field.")
        return value

    def text(self, value, path, required=False):
        if value is None or (type(value) is str and not value.strip()):
            if required:
                self.error("REQUIRED_FIELD", path, "Nonblank text is required.")
            return None
        if type(value) is not str:
            self.error("INVALID_TYPE", path, "Expected text.")
            return None
        return value.strip()

    def enum(self, value, path, choices, default=None):
        if value is None:
            if default is not None:
                return default
            self.error("REQUIRED_FIELD", path, "An explicit choice is required.")
            return None
        if type(value) is not str or value not in choices:
            self.error("INVALID_CHOICE", path, f"Expected one of {sorted(choices)}.")
            return None
        return value

    def items(self, value, path):
        if value is None:
            return ()
        if type(value) is not tuple:
            self.error("INVALID_SHAPE", path, "Expected a list.")
            return ()
        return value

    def names(self, value, path, choices=None):
        names = []
        for i, item in enumerate(self.items(value, path)):
            name = (
                self.enum(item, f"{path}[{i}]", choices)
                if choices
                else self.text(item, f"{path}[{i}]", required=True)
            )
            if name is not None:
                if name in names:
                    self.error("DUPLICATE_REFERENCE", path, "Duplicate list entry.")
                names.append(name)
        return tuple(names)

    def number(self, value, path):
        if type(value) not in (str, int, float):
            self.error(
                "INVALID_NUMBER", path, "Expected a finite numeric value, not Boolean."
            )
            return None
        if type(value) is str and not _NUMBER.fullmatch(value.strip()):
            self.error("INVALID_NUMBER", path, "Expected a decimal number.")
            return None
        try:
            result = float(value)
        except (ValueError, OverflowError):
            result = math.inf
        if not math.isfinite(result):
            self.error("INVALID_NUMBER", path, "Number must be finite.")
            return None
        return result

    def quantity(self, value, path, family, velocity=False):
        if value is None:
            return None
        obj = self.obj(value, path, {"value", "unit"})
        unit = self.text(obj.get("unit"), path + ".unit", required=True)
        number = self.number(obj.get("value"), path + ".value")
        if velocity and unit in _UNITS["velocity"][1]:
            family = "velocity"
        canonical, factors = _UNITS[family]
        if unit not in factors:
            self.error(
                "UNSUPPORTED_UNIT", path + ".unit", f"Supported units: {list(factors)}."
            )
            return None
        if number is None:
            return None
        result = number * factors[unit]
        if number <= 0 or not math.isfinite(result) or result <= 0:
            self.error(
                "INVALID_QUANTITY",
                path,
                "Final canonical quantity must be finite and positive.",
            )
            return None
        return RequestQuantity(result, canonical, obj["value"], obj["unit"])

    def origin(self, value, path):
        if value is None:
            return MappingProxyType({})
        obj = self.obj(
            value, path, {"kind", "raw_label", "source", "version", "target", "epoch"}
        )
        if "kind" in obj:
            self.enum(
                obj["kind"],
                path + ".kind",
                {"USER_DECLARED", "OT_COPIED", "IMPORTED", "UNKNOWN"},
            )
        for key in obj.keys() - {"kind"}:
            self.text(obj[key], path + "." + key)
        return MappingProxyType(dict(obj))

    def frequency(self, value, path):
        if value is None:
            return None
        obj = self.obj(value, path, {"value", "unit", "kind", "frame", "origin"})
        q = self.quantity(
            {k: obj[k] for k in ("value", "unit") if k in obj}, path, "frequency"
        )
        kind = self.enum(
            obj.get("kind"), path + ".kind", {"SKY", "REST", "UNKNOWN"}, "UNKNOWN"
        )
        frame = self.enum(obj.get("frame"), path + ".frame", _FRAMES, "UNKNOWN")
        origin = self.origin(obj.get("origin"), path + ".origin")
        if kind == "REST":
            self.capability(
                path,
                "Rest-frequency conversion is not implemented; spatial search remains possible.",
            )
        elif kind == "UNKNOWN" or frame == "UNKNOWN":
            self.missing(
                path,
                "Frequency reference is not sufficiently specified.",
                "CONT-FREQ/LINE-COVERAGE",
            )
        return RequestFrequency(q, kind, frame, origin) if q else None

    def position(self, value):
        path = "request.position"
        if value is None:
            return None
        obj = self.obj(value, path, {"ra", "dec", "ra_format", "dec_format", "frame"})
        self.enum(obj.get("frame"), path + ".frame", {"ICRS"})
        ra_format = self.enum(obj.get("ra_format"), path + ".ra_format", {"DEG", "HMS"})
        dec_format = self.enum(
            obj.get("dec_format"), path + ".dec_format", {"DEG", "DMS"}
        )

        def angle(raw, fmt, field, maximum):
            if fmt == "DEG":
                return self.number(raw, field)
            if fmt not in {"HMS", "DMS"}:
                return None
            match = (
                re.fullmatch(
                    r"([+-]?)(\d{1,3}):(\d{1,2}):(\d{1,2}(?:\.\d*)?)", raw.strip()
                )
                if type(raw) is str
                else None
            )
            if not match:
                self.error(
                    "INVALID_COORDINATE",
                    field,
                    "Use colon-separated sexagesimal coordinates.",
                )
                return None
            sign, first, minute, second = match.groups()
            first, minute, second = int(first), int(minute), float(second)
            if (
                minute >= 60
                or second >= 60
                or first > maximum
                or (first == maximum and (minute or second))
                or (fmt == "HMS" and (sign == "-" or first == 24))
            ):
                self.error(
                    "INVALID_COORDINATE",
                    field,
                    "Sexagesimal components outside allowed range.",
                )
                return None
            return (
                (-1 if sign == "-" else 1)
                * (first + minute / 60 + second / 3600)
                * (15 if fmt == "HMS" else 1)
            )

        ra = angle(obj.get("ra"), ra_format, path + ".ra", 24)
        dec = angle(obj.get("dec"), dec_format, path + ".dec", 90)
        if ra is not None and not 0 <= ra < 360:
            self.error(
                "INVALID_COORDINATE", path + ".ra", "RA must be in [0, 360) degrees."
            )
        if dec is not None and not -90 <= dec <= 90:
            self.error(
                "INVALID_COORDINATE", path + ".dec", "Dec must be in [-90, 90] degrees."
            )
        return RequestPosition(ra, dec) if ra is not None and dec is not None else None

    def window(self, obj, path):
        obj = self.obj(
            obj,
            path,
            {
                "window_id",
                "representation",
                "center",
                "bandwidth",
                "bandwidth_kind",
                "lower",
                "upper",
                "correlator_mode",
                "mode_origin",
                "channel_spacing",
                "spectral_resolution",
            },
        )
        identifier = self.text(obj.get("window_id"), path + ".window_id", True)
        representation = self.enum(
            obj.get("representation"),
            path + ".representation",
            {"CENTER_BANDWIDTH", "BOUNDS", "PARTIAL"},
            "PARTIAL",
        )
        center = self.frequency(obj.get("center"), path + ".center")
        lower = self.frequency(obj.get("lower"), path + ".lower")
        upper = self.frequency(obj.get("upper"), path + ".upper")
        width = self.quantity(obj.get("bandwidth"), path + ".bandwidth", "frequency")
        kind = self.enum(
            obj.get("bandwidth_kind"),
            path + ".bandwidth_kind",
            {"NOMINAL", "USABLE", "UNKNOWN"},
            "UNKNOWN",
        )
        mode = self.enum(
            obj.get("correlator_mode"),
            path + ".correlator_mode",
            {"FDM", "TDM", "UNKNOWN"},
            "UNKNOWN",
        )
        mode_origin = self.origin(obj.get("mode_origin"), path + ".mode_origin")
        spacing = self.quantity(
            obj.get("channel_spacing"), path + ".channel_spacing", "width"
        )
        resolution = self.quantity(
            obj.get("spectral_resolution"), path + ".spectral_resolution", "width"
        )
        interval = None
        lo = hi = None
        if width and (lower or upper):
            self.error(
                "CONFLICTING_REPRESENTATION",
                path,
                "Width plus coverage bounds is ambiguous; choose one interval representation.",
            )
        if representation == "CENTER_BANDWIDTH" and (lower or upper):
            self.error(
                "CONFLICTING_REPRESENTATION",
                path,
                "Center/width representation cannot contain bounds.",
            )
        if representation == "BOUNDS" and width:
            self.error(
                "CONFLICTING_REPRESENTATION",
                path,
                "Bounds representation cannot also contain bandwidth.",
            )
        origin = "BOUNDS_MIDPOINT_NOT_SPW_CENTER"
        if lower and upper:
            if (lower.kind, lower.frame) != (upper.kind, upper.frame):
                self.capability(
                    path,
                    "Bounds retained; compatible references needed before interval arithmetic.",
                    code="UNRESOLVED_SEMANTICS",
                )
            else:
                lo, hi = lower.quantity.value, upper.quantity.value
        elif center and width and kind != "USABLE":
            lo, hi = (
                center.quantity.value - width.value / 2,
                center.quantity.value + width.value / 2,
            )
            origin = "CENTER_BANDWIDTH"
        elif center and width:
            self.missing(
                path,
                "Usable width has no evidenced placement; coverage is not inferred.",
                "LINE-COVERAGE",
            )
        if lo is not None and hi is not None:
            span = hi - lo
            midpoint = lo + span / 2
            if (
                not all(math.isfinite(v) for v in (lo, hi, span, midpoint))
                or not 0 < lo < hi
                or not lo < midpoint < hi
            ):
                self.error(
                    "INVALID_INTERVAL",
                    path,
                    "Derived endpoints/span/midpoint must be finite, positive and noncollapsed.",
                )
            else:
                interval = RequestInterval(lo, hi, midpoint, span, kind, origin)
        return ProposedWindow(
            identifier,
            representation,
            center,
            width,
            kind,
            lower,
            upper,
            interval,
            mode,
            mode_origin,
            spacing,
            resolution,
        )

    def sensitivity(self, value, path, setup_id, windows):
        obj = self.obj(
            value,
            path,
            {
                "sensitivity_id",
                "purpose",
                "scope",
                "setup_id",
                "window_ids",
                "rms",
                "basis",
                "aggregate_path",
                "reference_frequency",
                "bandwidth_used_for_sensitivity",
                "bandwidth_meaning",
                "bandwidth_origin",
                "target_aggregate_bandwidth",
                "smoothing_resolution",
                "context",
            },
        )
        identifier = self.text(
            obj.get("sensitivity_id"), path + ".sensitivity_id", True
        )
        purpose = self.enum(
            obj.get("purpose"), path + ".purpose", {"CONTINUUM", "LINE"}
        )
        scope = self.enum(
            obj.get("scope"),
            path + ".scope",
            {"SETUP", "WINDOW", "UNRESOLVED"},
            "UNRESOLVED",
        )
        ids = self.names(obj.get("window_ids"), path + ".window_ids")
        for identifier_ref in ids:
            if identifier_ref not in windows:
                self.error(
                    "DANGLING_REFERENCE",
                    path + ".window_ids",
                    f"Unknown window {identifier_ref}.",
                )
        setup_ref = self.text(obj.get("setup_id"), path + ".setup_id")
        if setup_ref is not None and setup_ref != setup_id:
            self.error("DANGLING_REFERENCE", path + ".setup_id", "Unknown setup.")
        if scope == "SETUP" and setup_ref is None:
            self.error(
                "REQUIRED_FIELD",
                path + ".setup_id",
                "SETUP scope requires its setup ID.",
            )
        if scope == "WINDOW" and len(ids) != 1:
            self.error(
                "INVALID_ASSOCIATION",
                path + ".window_ids",
                "WINDOW scope requires exactly one window.",
            )
        basis = self.enum(
            obj.get("basis"),
            path + ".basis",
            {"AGGREGATE", "NATIVE_CHANNEL", "SMOOTHED", "UNKNOWN"},
            "UNKNOWN",
        )
        if scope == "SETUP" and (
            purpose == "LINE" or basis in {"NATIVE_CHANNEL", "SMOOTHED"}
        ):
            self.error(
                "INVALID_ASSOCIATION",
                path + ".scope",
                "Channel RMS requires WINDOW or explicitly UNRESOLVED scope.",
            )
        if basis == "AGGREGATE" and (purpose != "CONTINUUM" or scope == "WINDOW"):
            self.error(
                "INVALID_ASSOCIATION",
                path,
                "Aggregate continuum RMS uses setup or unresolved scope.",
            )
        route = None
        if basis == "AGGREGATE":
            route = self.enum(
                obj.get("aggregate_path"),
                path + ".aggregate_path",
                {"DIRECT_DECLARATION", "CONVERT_FROM_REFERENCE"},
            )
        elif obj.get("aggregate_path") is not None:
            self.error(
                "INVALID_ASSOCIATION",
                path + ".aggregate_path",
                "Aggregate path only belongs to aggregate basis.",
            )
        rms = self.quantity(obj.get("rms"), path + ".rms", "rms")
        frequency = self.frequency(
            obj.get("reference_frequency"), path + ".reference_frequency"
        )
        bandwidth = self.quantity(
            obj.get("bandwidth_used_for_sensitivity"),
            path + ".bandwidth_used_for_sensitivity",
            "width",
            velocity=True,
        )
        meaning = self.enum(
            obj.get("bandwidth_meaning"),
            path + ".bandwidth_meaning",
            {"EFFECTIVE_CHANNEL", "AGGREGATE", "USER_DEFINED", "UNKNOWN"},
            "UNKNOWN",
        )
        if basis in {"NATIVE_CHANNEL", "SMOOTHED"} and meaning == "AGGREGATE":
            self.error(
                "CONFLICTING_BASIS",
                path + ".bandwidth_meaning",
                "A channel RMS cannot declare aggregate noise bandwidth.",
            )
        if route == "DIRECT_DECLARATION" and meaning == "EFFECTIVE_CHANNEL":
            self.error(
                "CONFLICTING_BASIS",
                path + ".bandwidth_meaning",
                "Direct aggregate RMS cannot declare a per-channel noise basis.",
            )
        origin = self.origin(obj.get("bandwidth_origin"), path + ".bandwidth_origin")
        target = self.quantity(
            obj.get("target_aggregate_bandwidth"),
            path + ".target_aggregate_bandwidth",
            "width",
        )
        smoothing = self.quantity(
            obj.get("smoothing_resolution"),
            path + ".smoothing_resolution",
            "width",
            velocity=True,
        )
        context = self.obj(
            obj.get("context", {}),
            path + ".context",
            {
                "stokes_basis",
                "polarization_basis",
                "beam_context",
                "weighting_context",
                "smoothing",
                "spectral_averaging",
                "velocity_convention",
                "method",
            },
        )
        # Context is opaque provenance, not validated numerical comparison evidence.
        if not rms:
            self.missing(path + ".rms", "RMS is absent.", "CONT-RMS/LINE-RMS")
        if scope == "UNRESOLVED":
            self.missing(
                path + ".scope", "RMS scope is unresolved.", "CONT-RMS/LINE-RMS"
            )
        if basis == "UNKNOWN":
            self.missing(path + ".basis", "RMS basis is unknown.", "CONT-RMS/LINE-RMS")
        if basis in {"NATIVE_CHANNEL", "SMOOTHED"}:
            if not bandwidth:
                self.missing(
                    path + ".bandwidth_used_for_sensitivity",
                    "Noise bandwidth is missing; resolution is not a substitute.",
                    "LINE-RMS",
                )
            elif meaning == "UNKNOWN":
                self.missing(
                    path + ".bandwidth_meaning",
                    "Noise width exists but its meaning is unspecified.",
                    "LINE-RMS",
                )
            if (
                len(ids) == 1
                and ids[0] in windows
                and not windows[ids[0]].spectral_resolution
            ):
                self.missing(
                    path + ".window_ids",
                    "Linked window lacks spectral resolution.",
                    "LINE-RMS",
                )
        if route == "CONVERT_FROM_REFERENCE":
            for key, item in (
                ("bandwidth_used_for_sensitivity", bandwidth),
                ("target_aggregate_bandwidth", target),
            ):
                if item is None:
                    self.missing(
                        path + "." + key,
                        "Required for conversion, not for preserving the reference RMS.",
                        "CONT-RMS",
                    )
            self.capability(
                path,
                "Aggregate RMS conversion is not implemented; supplied RMS remains a reference value.",
                "CONT-RMS",
            )
        if basis == "SMOOTHED":
            if smoothing is None:
                self.missing(
                    path + ".smoothing_resolution",
                    "Smoothed resolution is absent.",
                    "LINE-RMS",
                )
            self.capability(
                path, "Automatic sensitivity smoothing is not implemented.", "LINE-RMS"
            )
        if any(q and q.unit == "km/s" for q in (bandwidth, smoothing)):
            self.capability(
                path,
                "Velocity width preserved; noise/frequency conversion is not implemented.",
                "LINE-RMS",
            )
        return ProposedSensitivity(
            identifier,
            purpose,
            scope,
            setup_ref,
            ids,
            rms,
            basis,
            route,
            frequency,
            bandwidth,
            meaning,
            origin,
            target,
            smoothing,
            MappingProxyType(dict(context)),
        )

    def search(self, value):
        path = "search_options"
        obj = self.obj(value, path, {"radius", "sources", "result_limit", "predicates"})
        radius = self.quantity(obj.get("radius"), path + ".radius", "radius")
        if radius and radius.value > 180:
            self.error(
                "INVALID_RADIUS",
                path + ".radius",
                "Radius must not exceed 180 degrees.",
            )
        sources = self.names(
            obj.get("sources"), path + ".sources", {"ARCHIVE", "QUEUE"}
        )
        limit = obj.get("result_limit")
        if limit is not None and (type(limit) is not int or limit <= 0):
            self.error(
                "INVALID_LIMIT",
                path + ".result_limit",
                "Result limit must be a positive integer.",
            )
        predicates = []
        for i, item in enumerate(
            self.items(obj.get("predicates"), path + ".predicates")
        ):
            p = f"{path}.predicates[{i}]"
            item = self.obj(
                item, p, {"field", "operator", "quantity", "basis", "context"}
            )
            field = self.enum(
                item.get("field"),
                p + ".field",
                {
                    "frequency",
                    "angular_resolution",
                    "spectral_resolution",
                    "sensitivity",
                },
            )
            operator = self.enum(
                item.get("operator"), p + ".operator", {"<", "<=", "=", ">=", ">"}
            )
            family = {
                "frequency": "frequency",
                "angular_resolution": "angle",
                "spectral_resolution": "width",
                "sensitivity": "rms",
            }.get(field, "frequency")
            q = self.quantity(item.get("quantity"), p + ".quantity", family)
            if item.get("quantity") is None:
                self.error(
                    "REQUIRED_FIELD", p + ".quantity", "A predicate needs a value/unit."
                )
            basis = (
                self.enum(
                    item.get("basis"),
                    p + ".basis",
                    {"AGGREGATE", "NATIVE_CHANNEL", "SMOOTHED", "UNKNOWN"},
                    "UNKNOWN",
                )
                if field == "sensitivity"
                else self.text(item.get("basis"), p + ".basis")
            )
            context = self.obj(
                item.get("context", {}),
                p + ".context",
                {
                    "frequency_reference",
                    "reference_frequency",
                    "bandwidth_used_for_sensitivity",
                    "origin",
                },
            )
            if field == "sensitivity" and basis == "UNKNOWN":
                self.missing(
                    p + ".basis", "Unresolved RMS filter must not be silently applied."
                )
            if q:
                predicates.append(
                    CandidatePredicate(
                        field, operator, q, basis, MappingProxyType(dict(context))
                    )
                )
        return SearchOptions(
            radius, sources, limit, tuple(predicates), MappingProxyType(dict(obj))
        )


def validate_proposed_observation(
    request_input, search_options_input=None
) -> RequestValidationResult:
    """Return detached inputs and diagnostics; any error suppresses both outputs.

    Search READY means adequate inputs for bounded spatial retrieval, not that
    every predicate can be applied or any duplication rule can be evaluated.
    """
    v = _Validator()
    raw = v.snapshot(request_input, "request")
    raw_options = v.snapshot(
        {} if search_options_input is None else search_options_input, "search_options"
    )
    obj = v.obj(
        raw,
        "request",
        {
            "target_kind",
            "geometry",
            "target_name",
            "position",
            "setup_id",
            "setup_complete",
            "intents",
            "angular_resolution",
            "representative_frequency",
            "representative_window_id",
            "spectral_windows",
            "sensitivities",
            "array_context",
        },
    )
    kind = v.enum(
        obj.get("target_kind"), "request.target_kind", {"FIXED", "MOVING", "SUN"}
    )
    geometry = v.enum(
        obj.get("geometry"), "request.geometry", {"SINGLE_POINTING", "MOSAIC"}
    )
    name = v.text(obj.get("target_name"), "request.target_name")
    position = v.position(obj.get("position"))
    setup = v.text(obj.get("setup_id"), "request.setup_id", True)
    complete = obj.get("setup_complete")
    if complete is not None and type(complete) is not bool:
        v.error(
            "INVALID_TYPE",
            "request.setup_complete",
            "Use Boolean or missing; this describes list completeness only.",
        )
    intents = v.names(obj.get("intents"), "request.intents", {"CONTINUUM", "LINE"})
    angle = v.quantity(
        obj.get("angular_resolution"), "request.angular_resolution", "angle"
    )
    representative = v.frequency(
        obj.get("representative_frequency"), "request.representative_frequency"
    )
    representative_id = v.text(
        obj.get("representative_window_id"), "request.representative_window_id"
    )
    windows = tuple(
        v.window(item, f"request.spectral_windows[{i}]")
        for i, item in enumerate(
            v.items(obj.get("spectral_windows"), "request.spectral_windows")
        )
    )
    by_id = {}
    for window in windows:
        if window.window_id in by_id:
            v.error(
                "DUPLICATE_ID", "request.spectral_windows", "Window IDs must be unique."
            )
        by_id[window.window_id] = window
    if representative_id is not None and representative_id not in by_id:
        v.error(
            "DANGLING_REFERENCE",
            "request.representative_window_id",
            "Representative window does not exist.",
        )
    elif representative_id and representative:
        window = by_id[representative_id]
        reference = window.lower or window.center
        if (
            window.interval
            and window.interval.kind == "NOMINAL"
            and reference
            and (representative.kind, representative.frame)
            == (reference.kind, reference.frame)
            and representative.kind != "UNKNOWN"
            and representative.frame != "UNKNOWN"
        ):
            if (
                not window.interval.lower_ghz
                <= representative.quantity.value
                <= window.interval.upper_ghz
            ):
                v.error(
                    "INVALID_ASSOCIATION",
                    "request.representative_frequency",
                    "Representative frequency outside its declared window interval.",
                )
        else:
            v.missing(
                "request.representative_frequency",
                "Window membership cannot yet be verified.",
            )
    sensitivities = tuple(
        v.sensitivity(item, f"request.sensitivities[{i}]", setup, by_id)
        for i, item in enumerate(
            v.items(obj.get("sensitivities"), "request.sensitivities")
        )
    )
    if len({s.sensitivity_id for s in sensitivities}) != len(sensitivities):
        v.error(
            "DUPLICATE_ID", "request.sensitivities", "Sensitivity IDs must be unique."
        )
    array = v.obj(
        obj.get("array_context", {}), "request.array_context", {"description", "origin"}
    )
    options = v.search(raw_options)
    if kind == "FIXED" and position is None:
        v.missing("request.position", "Position is needed for fixed-target search.")
    if options.radius is None:
        v.missing(
            "search_options.radius", "Explicit radius is needed for bounded search."
        )
    if not options.sources:
        v.missing("search_options.sources", "Select at least one source.")
    if kind == "FIXED" and geometry == "SINGLE_POINTING":
        if angle is None:
            v.missing(
                "request.angular_resolution",
                "Requested angular resolution is absent.",
                "ANGULAR",
            )
        if "LINE" in intents:
            if not windows:
                v.missing(
                    "request.spectral_windows",
                    "No line window centers supplied.",
                    "LINE-COVERAGE",
                )
            for i, window in enumerate(windows):
                p = f"request.spectral_windows[{i}]"
                if window.center is None:
                    v.missing(
                        p + ".center",
                        "A coverage midpoint is not a requested SPW center.",
                        "LINE-COVERAGE",
                    )
                if window.correlator_mode == "UNKNOWN":
                    v.missing(
                        p + ".correlator_mode",
                        "Mode evidence is unknown.",
                        "LINE-COVERAGE",
                    )
            if complete is not True:
                v.missing(
                    "request.setup_complete",
                    "Listed windows cannot support an exhaustive negative line conclusion.",
                    "LINE-COVERAGE",
                )
        if "CONTINUUM" in intents:
            if representative is None:
                v.missing(
                    "request.representative_frequency",
                    "No independent setup frequency supplied.",
                    "CONT-FREQ",
                )
            if not windows or any(w.bandwidth is None for w in windows):
                v.missing(
                    "request.spectral_windows",
                    "Width evidence for setup qualification is incomplete.",
                    "CONT-SETUP",
                )
            v.capability(
                "request.spectral_windows",
                "Policy width interpretation is not an implemented qualification method.",
                "CONT-SETUP",
                "UNRESOLVED_SEMANTICS",
            )
        for intent in intents:
            if not any(s.purpose == intent for s in sensitivities):
                v.missing(
                    "request.sensitivities",
                    f"No {intent} RMS evidence supplied.",
                    "CONT-RMS" if intent == "CONTINUUM" else "LINE-RMS",
                )
    errors = any(i.category == "ERROR" for i in v.issues)
    if errors:
        return RequestValidationResult(
            raw, raw_options, None, None, tuple(v.issues), SearchReadiness.BLOCKED
        )
    request = ProposedObservationRequest(
        kind,
        geometry,
        name,
        position,
        setup,
        complete,
        intents,
        angle,
        representative,
        representative_id,
        windows,
        sensitivities,
        MappingProxyType(dict(array)),
        raw,
    )
    if kind == "SUN":
        readiness = SearchReadiness.NOT_APPLICABLE
    elif kind == "MOVING" or geometry == "MOSAIC":
        readiness = SearchReadiness.UNSUPPORTED
        v.capability(
            "request",
            "First search implementation supports fixed single-pointing targets only.",
        )
    elif position is not None and options.radius and options.sources:
        readiness = SearchReadiness.READY
    else:
        readiness = SearchReadiness.BLOCKED
    return RequestValidationResult(
        raw, raw_options, request, options, tuple(v.issues), readiness
    )
