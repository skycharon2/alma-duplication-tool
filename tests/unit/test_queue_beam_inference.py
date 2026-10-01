"""Approved beam decision table and exact canonical threshold boundaries."""

from dataclasses import replace
import math

import pytest

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_row_beam import (
    ACA_7M_THRESHOLDS,
    resolve_queue_beam_interpretation,
)
from tests.integration.test_queue_row_beam import source


def row(**kwargs):
    return parse_queue_csv_bytes(source(**kwargs)).row_inputs[0]


@pytest.mark.parametrize("band,table", ACA_7M_THRESHOLDS.items())
@pytest.mark.parametrize(
    "offset,diameters", [(-0.01, (7.0, 12.0)), (0, (7.0,)), (0.01, (7.0,))]
)
def test_every_band_strict_boundary(band, table, offset, diameters):
    r = row(
        use7="True",
        tp="False",
        changes={
            "Band": f"ALMA_RB_{int(band):02d}",
            "Req. Ang. Res.": str(round(table[1] + offset, 2)),
        },
    )
    beam = resolve_queue_beam_interpretation(r)
    assert beam.diameters_m == diameters
    assert beam.field_status == "ABSENT" and beam.standalone is None
    if len(diameters) == 1:
        assert beam.interpretation_kind == "7M_COMPATIBLE_INFERENCE"
    # Ref.Frequency never rescales the threshold.
    details = dict(beam.details(r))
    assert details["aca_7m_threshold_arcsec"] == str(table[1])
    assert details["threshold_representative_frequency_ghz"] == str(table[0])
    assert details["reference_frequency_raw"] == "338.5"


@pytest.mark.parametrize(
    "value,expected",
    [
        (math.nextafter(5.52, 0), (7.0, 12.0)),
        (5.52, (7.0,)),
        (math.nextafter(5.52, math.inf), (7.0,)),
    ],
)
def test_no_epsilon_at_band_six(value, expected):
    r = row(use7="True", changes={"Band": "ALMA_RB_06", "Req. Ang. Res.": str(value)})
    assert resolve_queue_beam_interpretation(r).diameters_m == expected


@pytest.mark.parametrize("value", [None, 0, -1, math.nan, math.inf, True])
def test_required_ar_unavailable(value):
    r = row(use7="True")
    ar = r.request.requested_angular_resolution_arcsec
    r = replace(
        r,
        request=replace(
            r.request,
            requested_angular_resolution_arcsec=(
                None if value is None else replace(ar, value=value)
            ),
        ),
    )
    b = resolve_queue_beam_interpretation(r)
    assert b.classification == "UNRESOLVED" and b.diameters_m == ()
    assert b.reasons[-1] == "ACA_7M_INFERENCE_EVIDENCE_UNAVAILABLE"
    # TP explicitly establishes both diameters even without usable AR.
    assert resolve_queue_beam_interpretation(
        replace(r, request=replace(r.request, use_tp=True))
    ).diameters_m == (7.0, 12.0)


@pytest.mark.parametrize("band", ["", "ALMA_RB_11", "6.0", "unknown"])
def test_missing_band_has_no_default(band):
    r = row(use7="True")
    r = replace(r, group_key=replace(r.group_key, band=band))
    assert resolve_queue_beam_interpretation(r).classification == "UNRESOLVED"


def test_wrong_ar_unit_and_duplicate_standalone_do_not_infer():
    r = row(use7="True")
    r = replace(
        r,
        request=replace(
            r.request,
            requested_angular_resolution_arcsec=replace(
                r.request.requested_angular_resolution_arcsec, canonical_unit="deg"
            ),
        ),
    )
    assert resolve_queue_beam_interpretation(r).classification == "UNRESOLVED"
    r = row(standalone="True")
    raw = replace(
        r.raw_row,
        declared_columns=r.raw_row.declared_columns + ("standAlone_ACA",),
        raw_values=r.raw_row.raw_values + ("False",),
    )
    b = resolve_queue_beam_interpretation(replace(r, raw_row=raw))
    assert b.classification == "UNRESOLVED" and b.field_status == "INVALID"
    assert b.raw_value == "True"


@pytest.mark.parametrize("field", ["use_7m", "use_tp"])
@pytest.mark.parametrize("value", [None, "False", 0, 1])
def test_invalid_typed_flags_never_become_false(field, value):
    r = row()
    r = replace(r, request=replace(r.request, **{field: value}))
    b = resolve_queue_beam_interpretation(r)
    assert b.classification == "UNRESOLVED"
    assert b.reasons == ("INVALID_ARRAY_FLAGS",)


def test_explicit_standalone_keeps_priority_and_deduplicates_tp():
    r = row(
        standalone="True", use7="False", tp="True", changes={"Req. Ang. Res.": "0.001"}
    )
    b = resolve_queue_beam_interpretation(r)
    assert b.diameters_m == (7.0, 12.0) and b.standalone is True
    assert "STANDALONE_WITHOUT_7M_REQUEST" in b.anomalies
    r = row(standalone="False", use7="True", tp="True")
    b = resolve_queue_beam_interpretation(r)
    assert b.diameters_m == (7.0, 12.0)
    assert {"SOURCE_NON_STANDALONE", "TP_12M_REQUESTED"} <= set(b.reasons)
