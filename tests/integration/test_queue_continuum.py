"""Independent Queue continuum numerics and full retained-context orchestration."""

from dataclasses import replace
from fractions import Fraction
import json

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.queue_continuum import (
    merge_intervals,
    evaluate_queue_continuum,
)
from tests.integration.test_candidate_search import queue_rows, SpyClient
from tests.integration.test_confirmed_continuum import payload, validated


def case(
    changes=None,
    *,
    rms=0.1,
    frequency=230,
    count=1,
    sources=("QUEUE",),
    intents=("CONTINUUM",),
):
    p = payload()
    p["request"]["representative_frequency"]["value"] = frequency
    p["request"]["sensitivities"][0]["rms"]["value"] = rms
    p["request"]["intents"] = list(intents)
    p["search_options"]["sources"] = list(sources)
    v = validated(p)
    base = {
        "RA": "201.365",
        "Dec": "-43.019",
        "Use 7-m?": "False",
        "Use TP?": "False",
        "Ref.Frequency": "230",
        "Ref.Freq.Width": "7500",
        "Req.Sensitivity": "0.15",
        "Req. Ang. Res.": "0.45",
        "Velocity": "0",
    }
    for n, centre in enumerate((226, 228, 232, 234), 1):
        base[f"Freq SPW {n}"] = str(centre)
        base[f"Bandwidth SPW {n}"] = "1875"
    q = queue_rows(*[base | (changes or {}) for _ in range(count)])
    s = search_candidates(
        v, queue_result=q, archive_client=SpyClient(error=RuntimeError("offline"))
    )
    r = evaluate_candidate_search(s, queue_continuum=True)
    return s, r, r.context_evaluations[0]


def rule(c, name):
    return next(r for r in c.criteria if r.criterion_id == name)


def test_complete_branch_and_unchanged_source_values():
    s, _, c = case()
    assert c.branches[0].status == "CRITERIA_MET"
    r = rule(c, "CONT-RMS")
    assert dict(r.derived)["aggregate_bandwidth_mhz"] == 7500
    assert dict(r.derived)["aggregate_rms_mjy"] == 0.15
    assert r.candidate.value == 0.15 and r.candidate.unit == "mJy"
    assert (
        s.queue.retained_rows[
            0
        ].context.evidence.row.spectral.sensitivity.requested_sensitivity_mjy.value
        == 0.15
    )
    records = json.loads(dict(r.details)["spw_evidence_json"])
    assert len(records) == 4 and {x["spw_number"] for x in records} == {1, 2, 3, 4}
    assert c.branches[0].method_version == "queue_continuum_branch_1"


@pytest.mark.parametrize(
    "sigma,outcome",
    [("0.02", "SATISFIED"), ("0.2", "SATISFIED"), ("0.20000000001", "NOT_SATISFIED")],
)
def test_rms_direction_and_exact_twofold_boundary(sigma, outcome):
    _, _, c = case({"Req.Sensitivity": sigma})
    assert rule(c, "CONT-RMS").outcome == outcome


@pytest.mark.parametrize(
    "frequency,outcome",
    [(299, "SATISFIED"), (299.00000001, "NOT_SATISFIED"), (177, "SATISFIED")],
)
def test_representative_frequency_threshold(frequency, outcome):
    _, _, c = case(frequency=frequency)
    assert rule(c, "CONT-FREQ").outcome == outcome


def test_no_reference_frequency_beam_fallback():
    _, _, c = case({"Ref.Frequency": "0"})
    assert rule(c, "POS-SINGLE").outcome == "SATISFIED"
    assert rule(c, "CONT-FREQ").outcome is None
    assert rule(c, "CONT-RMS").outcome is None
    assert c.branches[0].status == "INDETERMINATE"


def test_exact_union_overlap_touching_and_duplicate():
    f = Fraction
    assert merge_intervals([(f("99.5"), f("100.5")), (f(100), f(101))]) == (
        (f("99.5"), f(101)),
    )
    assert merge_intervals([(f(1), f(2)), (f(2), f(3)), (f(1), f(2))]) == (
        (f(1), f(3)),
    )
    _, _, c = case({f"Freq SPW {n}": "230" for n in range(1, 5)})
    assert dict(rule(c, "CONT-RMS").derived)["aggregate_bandwidth_mhz"] == 1875
    assert dict(rule(c, "CONT-RMS").derived)["aggregate_rms_mjy"] == 0.3
    assert rule(c, "CONT-RMS").outcome == "NOT_SATISFIED"


def test_portal_width_conversion_and_independent_sqrt():
    _, _, c = case(
        {"Req.Sensitivity": "2", "Ref.Freq.Width": "100"}
        | {f"Bandwidth SPW {n}": "1000" for n in range(1, 5)},
        rms=1,
    )
    r = rule(c, "CONT-RMS")
    assert dict(r.derived)["aggregate_bandwidth_mhz"] == 3750
    assert dict(r.derived)["aggregate_rms_mjy"] == pytest.approx(0.3265986323710904)
    assert all(
        x["nominal_bandwidth_mhz"] == 1000
        for x in json.loads(dict(r.details)["spw_evidence_json"])
    )


@pytest.mark.parametrize("changes", [{"Bandwidth SPW 2": "800"}])
def test_missing_evidence_no_partial_rms(changes):
    _, _, c = case(changes)
    assert rule(c, "CONT-RMS").outcome is None
    assert dict(rule(c, "CONT-RMS").derived)["aggregate_rms_mjy"] is None
    assert c.branches[0].status == "INDETERMINATE"


@pytest.mark.parametrize(
    "changes", [{"Use 7-m?": "True"}, {"Use TP?": "True"}, {"Mosaic": "Custom"}]
)
def test_scope_cannot_become_negative(changes):
    _, _, c = case(changes, frequency=400)
    assert c.branches[0].status == "INDETERMINATE"
    assert rule(c, "CONT-FREQ").outcome is None


def test_missing_proposal_rms_and_definite_failure_three_value():
    s, _, _ = case(frequency=400)
    req = replace(s.plan.validation.request, sensitivities=())
    s = replace(
        s, plan=replace(s.plan, validation=replace(s.plan.validation, request=req))
    )
    c = evaluate_candidate_search(s, queue_continuum=True).context_evaluations[0]
    assert rule(c, "CONT-RMS").outcome is None
    assert c.branches[0].status == "CRITERIA_NOT_MET"


def test_opt_in_display_limit_independent_line_and_source_failure():
    s, r, c = case(count=3, sources=("ARCHIVE", "QUEUE"), intents=("CONTINUUM", "LINE"))
    assert len(r.context_evaluations) == 3
    assert s.archive.status == "FAILED"
    assert c.branches[0].status == "CRITERIA_MET"
    assert c.branches[1].status == "INDETERMINATE"
    old = evaluate_candidate_search(s, queue_common=True)
    assert all(x.branches[0].status == "INDETERMINATE" for x in old.context_evaluations)


def test_cross_context_is_rejected():
    s, _, c = case()
    context = replace(c.candidate.context, context_id="another-context")
    with pytest.raises(ValueError, match="another context"):
        evaluate_queue_continuum(s.plan.validation.request, context, c.criteria[:2])


def test_cli_report_all_rows_strict_json(tmp_path, monkeypatch):
    from alma_duplicate.cli.evaluate import main
    import requests

    monkeypatch.setattr(
        requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network")
    )
    out = tmp_path / "report.json"
    assert (
        main(
            [
                "--request",
                "examples/queue_continuum/request.json",
                "--queue-csv",
                "examples/queue_continuum/queue.csv",
                "--queue-continuum",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    doc = json.loads(out.read_text(), parse_constant=lambda x: pytest.fail(x))
    contexts = doc["context_evaluations"]
    assert len(contexts) == 4
    from collections import Counter

    assert Counter(c["branches"][0]["status"] for c in contexts) == {
        "CRITERIA_MET": 1,
        "CRITERIA_NOT_MET": 1,
        "INDETERMINATE": 2,
    }
    assert doc["assessment"] == "NOT_AGGREGATED"


def test_invalid_reference_width_remains_source_failure():
    p = payload()
    p["search_options"]["sources"] = ["QUEUE"]
    q = queue_rows({"Ref.Freq.Width": "0"})
    s = search_candidates(validated(p), queue_result=q)
    r = evaluate_candidate_search(s, queue_continuum=True)
    assert not r.context_evaluations
    assert s.queue.status != "COMPLETED"


def test_direct_aggregation_cannot_override_common_scope():
    from alma_duplicate.rules.aggregation import aggregate_continuum
    s, report, c = case({'Use TP?':'True'}, frequency=400)
    branch = aggregate_continuum(c.candidate.context,
                                 (*report.request_criteria, *c.criteria),
                                 supported=True, queue_method=True)
    assert branch.status == 'INDETERMINATE'
