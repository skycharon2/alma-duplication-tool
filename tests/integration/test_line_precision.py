"""Decision precision survives preparation, unit conversion and serialization."""
import json
import math
from dataclasses import replace
from fractions import Fraction

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.reporting import json_value
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.model import CriterionOutcome as O
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_line_preparation import payload, planned, report, validate


def line_payload(frequency, width, unit="MHz"):
    p = payload()
    p["request"]["spectral_windows"][0]["center"].update(value=frequency, kind="SKY")
    p["request"]["sensitivities"][0]["smoothing_resolution"] = {"value": width, "unit": unit}
    p["request"]["sensitivities"][0]["rms"]["value"] = 100
    return p


def first_criteria(result):
    return {r.criterion_id: r for r in result.context_evaluations[0].line_pairs[0].criteria}


@pytest.mark.parametrize("direction,expected", [(-1, O.NOT_SATISFIED), (0, O.SATISFIED), (1, O.SATISFIED)])
@pytest.mark.parametrize("source", ["ARCHIVE", "QUEUE"])
def test_resolution_boundary_end_to_end(source, direction, expected):
    frequency, width = (225, .5) if source == "ARCHIVE" else (230, .9765625)
    requested = width if direction == 0 else math.nextafter(width, math.inf if direction > 0 else 0)
    p = line_payload(frequency, requested)
    if source == "ARCHIVE":
        result = report(p)
    else:
        p["search_options"]["sources"] = ["QUEUE"]
        row = {"Project Code": "2025.1.00001.S", "RA": "201.365", "Dec": "-43.019",
               "Use 7-m?": "False", "Use TP?": "False", "Polarization": "DOUBLE",
               "Req. Ang. Res.": "0.3", "Ref.Frequency": "230", "Velocity": "0",
               "Long Offset": "0", "Lat Offset": "0"}
        for n in range(1, 5):
            row.update({f"Freq SPW {n}": str(230 if n == 1 else 250+n),
                        f"Bandwidth SPW {n}": "1875", f"Spec.Res. SPW {n}": str(width)})
        result = evaluate_candidate_search(search_candidates(validate(p), queue_result=queue_rows(row)), queue_line=True)
    criteria = first_criteria(result)
    assert criteria["LINE-RESOLUTION-COMPATIBILITY"].outcome is expected
    assert criteria["LINE-RESOLUTION-COMPATIBILITY"].method_version.endswith("_2")
    assert criteria["LINE-RMS"].outcome is (None if direction < 0 else O.SATISFIED)
    # Strict JSON still works with additive exact evidence fields.
    json.dumps(json_value(result), allow_nan=False)


@pytest.mark.parametrize("value,unit", [(.9765625,"MHz"),(976.5625,"kHz"),(976562.5,"Hz"),(.0009765625,"GHz")])
def test_equivalent_units_have_identical_decision_operands(value, unit):
    evidence = planned(line_payload(230, value, unit))
    dv = Fraction(evidence.planned_resolution_kms_exact)
    assert dv == Fraction("299792.458") * Fraction("0.9765625") / 230000
    assert evidence.method_version == "proposed_line_preparation_2"


def test_rest_and_velocity_derivation_never_round_trip_through_display():
    p = line_payload(230, 1000, "m/s")
    p["request"]["spectral_windows"][0]["center"]["kind"] = "REST"
    p["request"]["source_redshift"] = .03
    evidence = planned(p)
    assert Fraction(evidence.sky_frequency_ghz_exact) == Fraction(23000, 103)
    assert evidence.planned_resolution_kms_exact == "1"
    # Display changes cannot change the saved decision operands.
    assert replace(evidence, planned_resolution_kms=0).planned_resolution_kms_exact == "1"


def test_missing_resolution_has_no_exact_operand():
    p = line_payload(230, 1)
    del p["request"]["sensitivities"][0]["smoothing_resolution"]
    assert planned(p).planned_resolution_kms_exact is None
