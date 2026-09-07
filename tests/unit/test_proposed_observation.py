from copy import deepcopy

import pytest

from alma_duplicate.request_validation import validate_proposed_observation


@pytest.mark.parametrize(
    "center,kind,frame,valid,unverified",
    [
        (105, "NOMINAL", "TOPOCENTRIC", False, False),
        (100.5, "NOMINAL", "TOPOCENTRIC", True, False),
        (99, "NOMINAL", "TOPOCENTRIC", True, False),
        (101, "NOMINAL", "TOPOCENTRIC", True, False),
        (105, "USABLE", "TOPOCENTRIC", True, False),
        (105, "NOMINAL", "UNKNOWN", True, True),
        (105, "NOMINAL", "LSRK", True, True),
    ],
)
def test_independent_nominal_center_membership(center, kind, frame, valid, unverified):
    raw = request()
    raw["spectral_windows"] = [
        {
            "window_id": "w1",
            "representation": "BOUNDS",
            "bandwidth_kind": kind,
            "lower": frequency(99),
            "upper": frequency(101),
            "center": frequency(center, frame=frame),
        }
    ]
    result = validate_proposed_observation(raw, options())
    assert result.is_valid is valid
    assert result.can_search is valid
    assert any(i.code == "INCOMPATIBLE_REFERENCE" for i in result.issues) is unverified
    if valid:
        assert result.request.spectral_windows[0].center.quantity.value == center
        assert result.request.spectral_windows[0].interval.midpoint_ghz == 100
    else:
        assert result.request is None and result.search_options is None
        assert any(
            i.code == "INVALID_ASSOCIATION" and i.path.endswith(".center")
            for i in result.errors
        )


@pytest.mark.parametrize("rms_present", [True, False])
def test_line_rms_missing_is_reported_per_window(rms_present):
    raw = request()
    raw.update(intents=["LINE"], setup_complete=True)
    raw["spectral_windows"] = [
        window(
            window_id=identifier,
            correlator_mode="FDM",
            spectral_resolution=quantity(1, "MHz"),
        )
        for identifier in ("w1", "w2")
    ]
    sensitivity = {
        "sensitivity_id": "r1",
        "purpose": "LINE",
        "scope": "WINDOW",
        "window_ids": ["w1"],
        "basis": "NATIVE_CHANNEL",
        "bandwidth_used_for_sensitivity": quantity(1, "MHz"),
        "bandwidth_meaning": "EFFECTIVE_CHANNEL",
    }
    if rms_present:
        sensitivity["rms"] = quantity(1, "mJy/beam")
    raw["sensitivities"] = [sensitivity]
    result = validate_proposed_observation(raw, options())
    assert result.is_valid and result.can_search
    missing = [i for i in result.issues if i.path.endswith("].sensitivities")]
    assert len(missing) == (1 if rms_present else 2)
    assert any("w2" in i.message for i in missing)
    assert all(
        i.category == "MISSING" and i.side == "PROPOSED" and i.rule_id == "LINE-RMS"
        for i in missing
    )
    assert result.request.sensitivities[0].window_ids == ("w1",)
    assert result.validation_version == "2"


@pytest.mark.parametrize(
    "field,value",
    [
        ("ra", "-1e-999"),
        ("ra", "1e-999"),
        ("dec", "90.00000000000000000001"),
        ("dec", "-90.00000000000000000001"),
    ],
)
def test_decimal_coordinate_errors_do_not_disappear_during_float_conversion(
    field, value
):
    raw = request()
    raw["position"][field] = value
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and not result.can_search
    assert result.request is None and result.search_options is None
    assert result.raw_input["position"][field] == value
    assert any(i.path == "request.position." + field for i in result.errors)


@pytest.mark.parametrize("value", ["-0", "-0.0", "0e-999", "180"])
def test_exact_zero_and_normal_coordinates_remain_valid(value):
    raw = request()
    raw["position"]["ra"] = value
    result = validate_proposed_observation(raw, options())
    assert result.is_valid and result.can_search
    assert result.request.position.ra_deg == float(value)


def quantity(value, unit):
    return {"value": value, "unit": unit}


def frequency(value=100, unit="GHz", kind="SKY", frame="TOPOCENTRIC"):
    return dict(quantity(value, unit), kind=kind, frame=frame)


def request():
    return {
        "target_kind": "FIXED",
        "geometry": "SINGLE_POINTING",
        "setup_id": "setup-1",
        "position": {
            "ra": "180",
            "dec": "-0.5",
            "ra_format": "DEG",
            "dec_format": "DEG",
            "frame": "ICRS",
        },
    }


def options():
    return {"radius": quantity(30, "arcsec"), "sources": ["ARCHIVE", "QUEUE"]}


def window(**kwargs):
    return dict(
        {
            "window_id": "w1",
            "center": frequency(),
            "bandwidth": quantity(2, "GHz"),
            "bandwidth_kind": "NOMINAL",
        },
        **kwargs,
    )


def aggregate(**kwargs):
    return dict(
        {
            "sensitivity_id": "r1",
            "purpose": "CONTINUUM",
            "scope": "SETUP",
            "setup_id": "setup-1",
            "basis": "AGGREGATE",
            "aggregate_path": "DIRECT_DECLARATION",
            "rms": quantity(1, "mJy/beam"),
        },
        **kwargs,
    )


def test_units_coordinates_and_raw_input_are_independent():
    first = request()
    first["angular_resolution"] = quantity(0.5, "arcsec")
    first["representative_frequency"] = frequency()
    first["sensitivities"] = [aggregate()]
    second = deepcopy(first)
    second["position"].update(
        ra="12:00:00", ra_format="HMS", dec="-00:30:00", dec_format="DMS"
    )
    second["angular_resolution"] = quantity(500, "mas")
    second["representative_frequency"] = frequency(100000, "MHz")
    second["sensitivities"][0]["rms"] = quantity(0.001, "Jy/beam")
    a = validate_proposed_observation(first, options())
    b = validate_proposed_observation(second, options())
    assert a.can_search and b.can_search
    assert a.request.position == b.request.position
    assert a.request.angular_resolution.value == b.request.angular_resolution.value
    assert (
        a.request.representative_frequency.quantity.value
        == b.request.representative_frequency.quantity.value
    )
    assert a.request.sensitivities[0].rms.value == b.request.sensitivities[0].rms.value
    assert b.raw_input["position"]["dec"] == "-00:30:00"


def test_input_snapshot_detaches_nested_values():
    raw = request()
    raw["spectral_windows"] = [window()]
    raw["array_context"] = {"description": ["original"]}
    opts = options()
    result = validate_proposed_observation(raw, opts)
    raw["spectral_windows"][0]["center"]["value"] = 999
    raw["array_context"]["description"].append("changed")
    opts["sources"].clear()
    assert result.request.spectral_windows[0].center.quantity.value == 100
    assert result.request.array_context["description"] == ("original",)
    assert len(result.search_options.sources) == 2
    with pytest.raises(TypeError):
        result.raw_input["position"]["ra"] = 1
    with pytest.raises(AttributeError):
        result.request.spectral_windows[0].window_id = "changed"


@pytest.mark.parametrize(
    "value",
    [
        -1,
        0,
        True,
        float("nan"),
        float("inf"),
        "NaN",
        "Infinity",
        "1_000",
        [],
        "bad",
        10**400,
    ],
)
def test_invalid_quantity_never_produces_request(value):
    raw = request()
    raw["angular_resolution"] = quantity(value, "arcsec")
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid
    assert result.request is result.search_options is None
    assert not result.can_search
    assert result.raw_input is not None and result.errors


@pytest.mark.parametrize(
    "ra,dec,rf,df",
    [
        (360, 0, "DEG", "DEG"),
        (-1, 0, "DEG", "DEG"),
        (0, 91, "DEG", "DEG"),
        ("24:00:00", 0, "HMS", "DEG"),
        ("12:60:00", 0, "HMS", "DEG"),
        ("12:00:60", 0, "HMS", "DEG"),
        (0, "-90:00:01", "DEG", "DMS"),
        (True, 0, "DEG", "DEG"),
        (0, float("nan"), "DEG", "DEG"),
    ],
)
def test_bad_coordinates_rejected(ra, dec, rf, df):
    raw = request()
    raw["position"].update(ra=ra, dec=dec, ra_format=rf, dec_format=df)
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and result.request is None


def test_three_widths_and_optional_smoothing_context_never_fill_each_other():
    raw = request()
    raw["spectral_windows"] = [
        window(
            channel_spacing=quantity(122, "kHz"),
            spectral_resolution=quantity(244000, "Hz"),
        )
    ]
    raw["sensitivities"] = [
        {
            "sensitivity_id": "r1",
            "purpose": "LINE",
            "scope": "WINDOW",
            "window_ids": ["w1"],
            "basis": "NATIVE_CHANNEL",
            "rms": quantity(1, "mJy/beam"),
            "bandwidth_used_for_sensitivity": quantity(0.325, "MHz"),
            "bandwidth_meaning": "EFFECTIVE_CHANNEL",
            "context": {"stokes_basis": "I", "spectral_averaging": {"factor": 1}},
        }
    ]
    result = validate_proposed_observation(raw, options())
    w = result.request.spectral_windows[0]
    assert (
        w.channel_spacing.value,
        w.spectral_resolution.value,
        result.request.sensitivities[0].bandwidth_used_for_sensitivity.value,
    ) == pytest.approx((0.122, 0.244, 0.325))
    del raw["sensitivities"][0]["bandwidth_used_for_sensitivity"]
    result = validate_proposed_observation(raw, options())
    assert result.can_search
    assert result.request.sensitivities[0].bandwidth_used_for_sensitivity is None
    assert any(i.path.endswith("bandwidth_used_for_sensitivity") for i in result.issues)


def test_direct_aggregate_without_windows_or_noise_width_is_valid():
    raw = request()
    raw.update(
        intents=["CONTINUUM"],
        representative_frequency=frequency(),
        sensitivities=[aggregate()],
    )
    result = validate_proposed_observation(raw, options())
    assert result.can_search
    assert not result.request.spectral_windows
    assert result.request.sensitivities[0].rms.value == 1
    assert not any(
        i.path.endswith("bandwidth_used_for_sensitivity") for i in result.issues
    )


def test_reference_aggregate_does_not_manufacture_converted_rms():
    raw = request()
    raw["sensitivities"] = [aggregate(aggregate_path="CONVERT_FROM_REFERENCE")]
    result = validate_proposed_observation(raw, options())
    assert result.can_search
    assert result.request.sensitivities[0].rms.value == 1
    assert {i.category for i in result.issues} >= {"MISSING", "CAPABILITY"}


def test_missing_requested_width_not_a_line_center_requirement():
    raw = request()
    raw.update(
        intents=["LINE"],
        setup_complete=True,
        spectral_windows=[
            {"window_id": "w1", "center": frequency(), "correlator_mode": "FDM"}
        ],
    )
    result = validate_proposed_observation(raw, options())
    assert result.can_search
    assert result.request.spectral_windows[0].interval is None
    assert not any(i.rule_id == "LINE-COVERAGE" for i in result.issues)


def test_bounds_midpoint_is_not_spw_center():
    raw = request()
    raw.update(
        intents=["LINE"],
        spectral_windows=[
            {
                "window_id": "w1",
                "representation": "BOUNDS",
                "lower": frequency(99),
                "upper": frequency(102),
                "bandwidth_kind": "USABLE",
            }
        ],
    )
    result = validate_proposed_observation(raw, options())
    w = result.request.spectral_windows[0]
    assert w.interval.midpoint_ghz == 100.5 and w.center is None
    assert not w.interval.scientifically_validated
    assert any(i.path.endswith(".center") for i in result.issues)


@pytest.mark.parametrize("kind", ["NOMINAL", "USABLE", "UNKNOWN"])
def test_interval_kind_is_not_promoted(kind):
    raw = request()
    raw["spectral_windows"] = [window(bandwidth_kind=kind)]
    result = validate_proposed_observation(raw, options())
    assert result.is_valid
    interval = result.request.spectral_windows[0].interval
    if kind == "USABLE":
        assert interval is None
    else:
        assert interval.kind == kind and not interval.scientifically_validated


@pytest.mark.parametrize(
    "change",
    [
        {"bandwidth": quantity(-1, "GHz")},
        {"center": frequency(1e308), "bandwidth": quantity(1.7e308, "GHz")},
        {"center": frequency(100), "bandwidth": quantity(1e-300, "GHz")},
        {"lower": frequency(101), "upper": frequency(99)},
    ],
)
def test_invalid_window_arithmetic(change):
    raw = request()
    w = {"window_id": "w1", "bandwidth_kind": "NOMINAL"}
    w.update(change)
    raw["spectral_windows"] = [w]
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and result.request is None


def test_canonical_overflow_and_underflow():
    for family_field, q in [
        ("angular_resolution", quantity(5e-324, "mas")),
        ("representative_frequency", frequency(5e-324, "Hz")),
    ]:
        raw = request()
        raw[family_field] = q
        assert not validate_proposed_observation(raw, options()).is_valid
    raw = request()
    raw["sensitivities"] = [aggregate(rms=quantity(1e308, "Jy/beam"))]
    assert not validate_proposed_observation(raw, options()).is_valid


def test_unit_unsupported_vs_method_unimplemented():
    raw = request()
    raw["representative_frequency"] = frequency(kind="REST", frame="UNKNOWN")
    result = validate_proposed_observation(raw, options())
    assert result.can_search and any(i.category == "CAPABILITY" for i in result.issues)
    raw["sensitivities"] = [aggregate(rms=quantity(1, "K"))]
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and any(
        i.code == "UNSUPPORTED_UNIT" for i in result.errors
    )


def test_representative_roles_and_no_usable_midpoint_assumption():
    raw = request()
    raw.update(
        spectral_windows=[window()],
        representative_window_id="w1",
        representative_frequency=frequency(100.5),
        sensitivities=[aggregate(reference_frequency=frequency(99.5))],
    )
    result = validate_proposed_observation(raw, options())
    assert result.is_valid
    assert result.request.spectral_windows[0].center.quantity.value == 100
    assert result.request.representative_frequency.quantity.value == 100.5
    assert result.request.sensitivities[0].reference_frequency.quantity.value == 99.5


@pytest.mark.parametrize(
    "mutation", ["duplicate", "dangling", "rms_scope", "representative", "dual"]
)
def test_bad_associations(mutation):
    raw = request()
    raw["spectral_windows"] = [window()]
    if mutation == "duplicate":
        raw["spectral_windows"].append(window())
    if mutation == "dangling":
        raw["sensitivities"] = [aggregate(window_ids=["missing"])]
    if mutation == "rms_scope":
        raw["sensitivities"] = [aggregate(scope="WINDOW", window_ids=["w1"])]
    if mutation == "representative":
        raw["representative_window_id"] = "missing"
    if mutation == "dual":
        raw["spectral_windows"][0]["lower"] = frequency(99)
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and not result.can_search


def test_search_predicates_keep_operator_and_do_not_fill_request():
    opts = options()
    opts["predicates"] = [
        {
            "field": "angular_resolution",
            "operator": "<",
            "quantity": quantity(0.5, "arcsec"),
        }
    ]
    result = validate_proposed_observation(request(), opts)
    assert result.can_search and result.request.angular_resolution is None
    assert result.search_options.predicates[0].operator == "<"
    assert result.search_options.predicates[0].quantity.value == 0.5


@pytest.mark.parametrize(
    "kind,geometry,expected",
    [
        ("MOVING", "SINGLE_POINTING", "UNSUPPORTED"),
        ("FIXED", "MOSAIC", "UNSUPPORTED"),
        ("SUN", "SINGLE_POINTING", "NOT_APPLICABLE"),
    ],
)
def test_unsupported_modes_preserved(kind, geometry, expected):
    raw = request()
    raw.update(target_kind=kind, geometry=geometry)
    result = validate_proposed_observation(raw, options())
    assert result.is_valid and result.request is not None
    assert result.search_readiness == expected and not result.can_search


@pytest.mark.parametrize("raw", [[], "bad", None, {"extra": 1}])
def test_bad_root_shape_returns_report(raw):
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and result.request is None


def test_cycles_and_unknown_field_rejected():
    raw = request()
    raw["cycle"] = raw
    result = validate_proposed_observation(raw, options())
    assert not result.is_valid and any(i.code == "CYCLIC_INPUT" for i in result.errors)


def test_missing_position_radius_or_sources_is_valid_but_not_search_ready():
    raw = request()
    raw.pop("position")
    result = validate_proposed_observation(raw, {})
    assert result.is_valid and result.request is not None
    assert result.search_readiness == "BLOCKED"
    assert all(i.category != "ERROR" for i in result.issues)


@pytest.mark.parametrize(
    "update",
    [
        {"radius": quantity(181, "deg")},
        {"radius": quantity(0, "arcsec")},
        {"result_limit": True},
        {"result_limit": 0},
        {"sources": "ARCHIVE"},
        {"sources": ["UNKNOWN"]},
        {"sources": ["ARCHIVE", "ARCHIVE"]},
        {"predicates": [{"field": "angular_resolution", "operator": "<"}]},
        {
            "predicates": [
                {
                    "field": "frequency",
                    "operator": "!=",
                    "quantity": quantity(100, "GHz"),
                }
            ]
        },
    ],
)
def test_invalid_search_options_also_suppress_request(update):
    opts = options()
    opts.update(update)
    report = validate_proposed_observation(request(), opts)
    assert not report.is_valid and report.request is report.search_options is None
    assert any(i.path.startswith("search_options") for i in report.errors)


def test_sensitivity_filter_retains_unknown_basis_without_applying_it():
    opts = options()
    opts["predicates"] = [
        {
            "field": "sensitivity",
            "operator": "<",
            "quantity": quantity(0.02, "mJy/beam"),
        }
    ]
    report = validate_proposed_observation(request(), opts)
    assert report.can_search
    assert report.search_options.predicates[0].basis == "UNKNOWN"
    assert any(i.path == "search_options.predicates[0].basis" for i in report.issues)


def test_conflicting_rms_basis_rejected():
    raw = request()
    raw["sensitivities"] = [aggregate(bandwidth_meaning="EFFECTIVE_CHANNEL")]
    report = validate_proposed_observation(raw, options())
    assert not report.is_valid and any(
        i.code == "CONFLICTING_BASIS" for i in report.errors
    )


def test_nominal_representative_membership_is_checked_but_usable_crop_is_not():
    raw = request()
    raw.update(
        representative_frequency=frequency(105),
        representative_window_id="w1",
        spectral_windows=[window()],
    )
    assert not validate_proposed_observation(raw, options()).is_valid
    raw["spectral_windows"] = [
        {
            "window_id": "w1",
            "center": frequency(105),
            "lower": frequency(100),
            "upper": frequency(101),
            "bandwidth_kind": "USABLE",
        }
    ]
    report = validate_proposed_observation(raw, options())
    assert report.can_search
    assert report.request.spectral_windows[0].center.quantity.value == 105
    assert report.request.spectral_windows[0].interval.midpoint_ghz == 100.5


def test_mismatched_bound_references_retained_without_arithmetic():
    raw = request()
    raw["spectral_windows"] = [
        {
            "window_id": "w1",
            "lower": frequency(100, frame="LSRK"),
            "upper": frequency(99, frame="TOPOCENTRIC"),
        }
    ]
    report = validate_proposed_observation(raw, options())
    assert report.is_valid and report.request.spectral_windows[0].interval is None
    assert any(i.code == "UNRESOLVED_SEMANTICS" for i in report.issues)
