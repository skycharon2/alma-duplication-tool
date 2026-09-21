"""Numerical guide B acceptance and coherent-pair regression cases."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.reporting import report_document
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.line import evaluate_line
from alma_duplicate.rules.model import MethodApproval
from tests.integration.test_line_preparation import EXAMPLE, payload, validate, report


@pytest.fixture(scope="module")
def source():
    return search_candidates(
        validate(),
        archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json"),
    ).archive.source_record


def evaluate(source, p=None, *, changes=None, rows=None):
    rows = (
        tuple(rows) if rows is not None else (dict(source.rows[0], **(changes or {})),)
    )
    source = replace(
        source,
        rows=rows,
        provenance=replace(
            source.provenance, expected_count=len(rows), retrieved_count=len(rows)
        ),
    )
    v = validate(p)
    assert v.is_valid, v.errors
    return evaluate_candidate_search(search_candidates(v, archive_result=source))


def results(r):
    pair = r.context_evaluations[0].line_pairs[0]
    return pair, {c.criterion_id: c for c in pair.criteria}


def sky_request(value=225.134765625):
    p = payload()
    p["request"]["spectral_windows"][0]["center"].update(kind="SKY", value=value)
    return p


def support(*, low=224.8, high=225.4, resolution="500kHz", sigma="0.4mJy/beam"):
    return f"[{low}..{high}GHz,{resolution},{sigma}@10km/s,1mJy/beam@native, XX YY]"


def test_guide_b_numerics_serialization_and_method_gates():
    r = report()
    pair, rules = results(r)
    rms = rules["LINE-RMS"]
    d = dict(rms.derived)
    assert d["sigma_at_plan_mjy_beam"] == pytest.approx(0.282842712474619, abs=1e-14)
    assert d["sigma_comp_mjy_beam"] == pytest.approx(0.4072935059634514, abs=1e-14)
    assert d["archive_resolution_kms"] == pytest.approx(
        299792.458 * 0.0005 / 225.134765625
    )
    assert pair.truth is Truth.TRUE and all(
        c.eligible_for_formal_aggregation for c in pair.criteria
    )
    assert all(c.decision_refs and c.method_version for c in pair.criteria)
    doc = report_document(r)
    assert doc["report_version"] == "4" and doc["evaluation_version"] == "5"
    assert doc["assessment"] == "NOT_AGGREGATED"
    assert doc["evaluation_scope"]["display_truncated"]
    assert [c["branches"][0]["status"] for c in doc["context_evaluations"]] == [
        "CRITERIA_MET",
        "CRITERIA_NOT_MET",
    ]
    assert len(doc["context_evaluations"]) == 2
    for item in doc["context_evaluations"]:
        pair = item["line_pairs"][0]
        assert pair["attempt"] == item["line_pairing"]["attempts"][0]
        assert all("eligible_for_formal_aggregation" in c for c in pair["criteria"])
    assert not any(
        i["category"] == "CAPABILITY" and (i["rule_id"] or "").startswith("LINE")
        for i in doc["request"]["issues"]
    )
    json.dumps(doc, allow_nan=False)


@pytest.mark.parametrize(
    "frequency,expected",
    [
        (224.8, True),
        (225.4, True),
        (224.79999999999998, False),
        (225.40000000000003, False),
    ],
)
def test_exact_coverage_includes_both_endpoints(source, frequency, expected):
    pair, rules = results(evaluate(source, sky_request(frequency)))
    assert (rules["LINE-COVERAGE"].outcome == "SATISFIED") is expected
    assert (pair.truth is Truth.TRUE) is expected


@pytest.mark.parametrize(
    "resolution,expected",
    [("19.999999999MHz", True), ("20MHz", True), ("20.000000001MHz", False)],
)
def test_resolution_inclusive_threshold_blocks_rms_when_coarse(
    source, resolution, expected
):
    p = sky_request(299.792458)
    _, rules = results(
        evaluate(
            source,
            p,
            changes={
                "frequency": 299.792458,
                "frequency_support": support(low=299, high=300, resolution=resolution),
            },
        )
    )
    assert (rules["LINE-RESOLUTION-COMPATIBILITY"].outcome == "SATISFIED") is expected
    rms = rules["LINE-RMS"]
    if expected:
        assert rms.outcome == "SATISFIED"
    else:
        assert rms.outcome is None
        assert "ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED" in rms.reasons
        assert dict(rms.derived)["sigma_at_plan_mjy_beam"] is None
        assert dict(rms.derived)["sigma_comp_mjy_beam"] is None


@pytest.mark.parametrize(
    "sigma,expected",
    [
        ("0.1mJy/beam", True),
        ("0.6mJy/beam", True),
        ("0.6000000000000001mJy/beam", False),
        ("1mJy/beam", False),
        ("0.0006Jy/beam", True),
    ],
)
def test_directional_rms_exact_two_and_units(source, sigma, expected):
    p = payload()
    p["request"]["sensitivities"][0]["smoothing_resolution"]["value"] = 10
    pair, rules = results(
        evaluate(
            source,
            p,
            changes={
                "spatial_resolution": 0.3,
                "frequency_support": support(sigma=sigma),
            },
        )
    )
    assert (rules["LINE-RMS"].outcome == "SATISFIED") is expected
    assert (pair.truth is Truth.TRUE) is expected


@pytest.mark.parametrize("theta_archive", [0.15, 0.25, 0.3, 0.6])
def test_angular_correction_direction_and_common_angular_rule(source, theta_archive):
    pair, rules = results(
        evaluate(source, changes={"spatial_resolution": theta_archive})
    )
    expected = 0.4 * (10 / 20) ** 0.5 * (0.3 / theta_archive) ** 2
    assert dict(rules["LINE-RMS"].derived)["sigma_comp_mjy_beam"] == pytest.approx(
        expected
    )
    assert (pair.truth is Truth.TRUE) is (expected <= 0.6)


def test_good_corrected_rms_does_not_replace_common_angular(source):
    pair, rules = results(evaluate(source, changes={"spatial_resolution": 0.61}))
    assert rules["LINE-RMS"].outcome == "SATISFIED"
    assert rules["ANGULAR"].outcome == "NOT_SATISFIED"
    assert pair.truth is Truth.FALSE


@pytest.mark.parametrize(
    "proposed,candidate,expected",
    [
        ("FDM", 128, "FALSE"),
        ("TDM", 1920, "FALSE"),
        ("UNKNOWN", 1920, "UNKNOWN"),
        ("FDM", None, "UNKNOWN"),
        ("UNKNOWN", 128, "FALSE"),
    ],
)
def test_mode_is_a_condition_not_pair_availability(
    source, proposed, candidate, expected
):
    p = payload()
    p["request"]["spectral_windows"][0]["correlator_mode"] = proposed
    pair, rules = results(evaluate(source, p, changes={"em_xel": candidate}))
    assert pair.attempt.reference is not None
    assert pair.truth.value == expected
    assert rules["LINE-COVERAGE"].outcome == "SATISFIED"


def test_missing_requested_rms_does_not_hide_other_conditions(source):
    p = payload()
    p["request"]["sensitivities"][0].pop("rms")
    pair, rules = results(evaluate(source, p))
    assert pair.truth is Truth.UNKNOWN and rules["LINE-RMS"].outcome is None
    assert all(rules[k].outcome == "SATISFIED" for k in rules if k != "LINE-RMS")
    assert "PLANNED_LINE_RMS_REQUIRED" in rules["LINE-RMS"].reasons
    p["request"]["spectral_windows"][0]["center"].update(value=240, kind="SKY")
    assert results(evaluate(source, p))[0].truth is Truth.FALSE


def two_windows(*, first=240, second=225.1, second_rms=0.01):
    p = sky_request(first)
    w = deepcopy(p["request"]["spectral_windows"][0])
    w.update(window_id="line-1")
    w["center"]["value"] = second
    p["request"]["spectral_windows"].append(w)
    s = deepcopy(p["request"]["sensitivities"][0])
    s.update(sensitivity_id="rms-1", window_ids=["line-1"])
    s["rms"]["value"] = second_rms
    p["request"]["sensitivities"].append(s)
    return p


def test_never_or_individual_conditions_across_pairs(source):
    item = evaluate(source, two_windows()).context_evaluations[0]
    assert [p.truth for p in item.line_pairs] == [Truth.FALSE, Truth.FALSE]
    assert item.branches[0].truth is Truth.FALSE
    first, second = [
        {c.criterion_id: c.outcome for c in p.criteria} for p in item.line_pairs
    ]
    assert first["LINE-RMS"] == second["LINE-COVERAGE"] == "SATISFIED"
    assert first["LINE-COVERAGE"] == second["LINE-RMS"] == "NOT_SATISFIED"


@pytest.mark.parametrize(
    "second_rms,remove_rms,expected",
    [(0.3, False, "TRUE"), (0.01, False, "FALSE"), (0.3, True, "UNKNOWN")],
)
def test_pair_or_true_false_unknown(source, second_rms, remove_rms, expected):
    p = two_windows(second_rms=second_rms)
    if remove_rms:
        p["request"]["sensitivities"][1].pop("rms")
    item = evaluate(source, p).context_evaluations[0]
    assert item.line_pairs[0].truth is Truth.FALSE
    assert item.branches[0].truth.value == expected


@pytest.mark.parametrize("frequency,expected", [(240, "UNKNOWN"), (225.1, "TRUE")])
def test_incomplete_enumeration_cannot_establish_negative(source, frequency, expected):
    p = sky_request(frequency)
    p["request"]["setup_complete"] = False
    branch = evaluate(source, p).context_evaluations[0].branches[0]
    assert branch.truth.value == expected
    assert "PROPOSED_ENUMERATION_INCOMPLETE" in branch.reasons


def test_empty_enumeration_is_unknown_even_if_marked_complete(source):
    p = payload()
    p["request"].update(spectral_windows=[], sensitivities=[])
    item = evaluate(source, p).context_evaluations[0]
    assert item.line_pairs == () and item.branches[0].truth is Truth.UNKNOWN
    assert "NO_PROPOSED_LINE_WINDOWS" in item.branches[0].reasons


def test_candidate_spws_cannot_borrow_coverage_rms_or_resolution(source):
    first = dict(source.rows[0], frequency_support=support(sigma="2mJy/beam"))
    second = dict(
        source.rows[1],
        em_xel=1920,
        frequency_support=support(low=239, high=241, sigma="0.01mJy/beam"),
    )
    r = evaluate(source, rows=[first, second])
    assert len(r.context_evaluations) == 2
    assert all(c.branches[0].truth is Truth.FALSE for c in r.context_evaluations)
    assert [
        dict(c.line_pairs[0].criteria[-1].derived)["sigma_10kms_mjy_beam"]
        for c in r.context_evaluations
    ] == [2, 0.01]
    # The row scalar is deliberately more favourable; the component still owns RMS.
    altered = evaluate(
        source,
        changes={
            "sensitivity_10kms": 0.00001,
            "frequency_support": support(sigma="2mJy/beam"),
        },
    )
    assert results(altered)[1]["LINE-RMS"].outcome == "NOT_SATISFIED"


def test_unapproved_common_condition_blocks_formal_positive(source):
    r = evaluate(source)
    item = r.context_evaluations[0]
    request = r.search_result.plan.validation.request
    common = tuple(
        replace(c, approval=MethodApproval.PROVISIONAL) for c in item.criteria
    )
    _, pairs, branch = evaluate_line(request, item.candidate.context, common)
    assert pairs[0].truth is branch.truth is Truth.UNKNOWN
    with pytest.raises(ValueError, match="another context"):
        evaluate_line(
            request,
            item.candidate.context,
            tuple(replace(c, context_id="another") for c in common),
        )
    with pytest.raises(ValueError, match="exactly"):
        evaluate_line(request, item.candidate.context, common + common)


def test_context_and_pair_contracts_reject_mismatched_results():
    first, second = report().context_evaluations
    with pytest.raises(ValueError, match="prepared attempts"):
        replace(first, line_pairs=second.line_pairs)
    with pytest.raises(ValueError, match="another context"):
        replace(first.line_pairs[0], criteria=second.line_pairs[0].criteria)


def test_unsupported_geometry_does_not_become_false_from_other_conditions(source):
    r = evaluate(
        source, changes={"is_mosaic": "T", "spatial_resolution": 20, "em_xel": 128}
    )
    assert r.context_evaluations[0].branches[0].truth is Truth.UNKNOWN
    assert all(p.truth is Truth.UNKNOWN for p in r.context_evaluations[0].line_pairs)


def test_no_pairs_or_line_branch_when_unselected(source):
    p = payload()
    p["request"]["intents"] = ["CONTINUUM"]
    item = evaluate(source, p).context_evaluations[0]
    assert item.line_pairing is None and item.line_pairs == ()
    assert [b.branch for b in item.branches] == ["CONTINUUM"]


@pytest.mark.parametrize(
    "changes",
    [
        {"em_xel": None},
        {"spatial_resolution": None},
        {"frequency_support": None},
        {"frequency_support": "[224.8..225.4GHz,500kHz,1mJy/beam@native, XX YY]"},
    ],
)
def test_missing_candidate_evidence_is_unknown(source, changes):
    r = evaluate(source, changes=changes)
    pair, rules = results(r)
    assert pair.truth is Truth.UNKNOWN
    assert any(rule.outcome is None and rule.reasons for rule in rules.values())
    assert r.context_evaluations[0].branches[0].truth is Truth.UNKNOWN


def test_resolution_conflict_blocks_rms_and_is_preserved_in_attempt(source):
    p = payload()
    p["request"]["spectral_windows"][0]["spectral_resolution"] = {
        "value": 19,
        "unit": "km/s",
    }
    pair, rules = results(evaluate(source, p))
    assert pair.truth is Truth.UNKNOWN
    assert "CONFLICTING_PLANNED_RESOLUTIONS" in pair.attempt.reasons
    assert rules["LINE-RESOLUTION-COMPATIBILITY"].outcome is None
    assert rules["LINE-RMS"].outcome is None
    assert dict(rules["LINE-RMS"].derived)["sigma_at_plan_mjy_beam"] is None


def test_unrepresentable_display_never_changes_exact_rms_comparison(source):
    p = payload()
    p["request"]["sensitivities"][0]["rms"]["value"] = 1e308
    pair, rules = results(
        evaluate(
            source,
            p,
            changes={
                "spatial_resolution": 0.001,
                "frequency_support": support(sigma="1e308mJy/beam"),
            },
        )
    )
    rms = rules["LINE-RMS"]
    assert rms.outcome == "NOT_SATISFIED"
    assert dict(rms.derived)["sigma_comp_mjy_beam"] is None
    assert "NUMERIC_DISPLAY_UNREPRESENTABLE" in rms.reasons
    assert dict(rms.details)["rms_ratio_squared_exact"]
    json.dumps(
        report_document(
            evaluate(
                source,
                p,
                changes={
                    "spatial_resolution": 0.001,
                    "frequency_support": support(sigma="1e308mJy/beam"),
                },
            )
        ),
        allow_nan=False,
    )


def test_queue_line_is_unknown_and_does_not_use_archive_mapping():
    from tests.integration.test_search_plan_spatial import queue

    p = payload()
    p["search_options"]["sources"] = ["QUEUE"]
    p["request"]["position"].update(ra=0, dec=0)
    q, _ = queue()
    r = evaluate_candidate_search(search_candidates(validate(p), queue_result=q))
    assert r.context_evaluations
    for item in r.context_evaluations:
        assert item.branches[0].truth is Truth.UNKNOWN
        assert all(pair.truth is Truth.UNKNOWN for pair in item.line_pairs)
        assert all(pair.attempt.reference is None for pair in item.line_pairs)
