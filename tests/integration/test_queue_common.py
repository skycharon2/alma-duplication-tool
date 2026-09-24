"""Confirmed Queue common criteria, independently of branch completion."""

from dataclasses import replace
import json
import math

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.cli.evaluate import main
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.queue_common import evaluate_queue_common
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_search_plan_spatial import validation, archive
from tests.integration.test_queue_candidate_beam import QUEUE, REQUEST
from alma_duplicate.search_plan import build_search_plan


def case(changes=None, *, dec=20, angular=0.3):
    q = queue_rows(
        {"RA": "10", "Dec": "20", "Ref.Frequency": "338.5", "Req. Ang. Res.": "0.45"}
        | (changes or {})
    )
    v = validation(sources=("QUEUE",), ra=10, dec=dec)
    v = replace(
        v,
        request=replace(
            v.request,
            angular_resolution=replace(v.request.angular_resolution, value=angular),
        ),
    )
    s = search_candidates(v, queue_result=q)
    row = s.queue.rows[0]
    return s, evaluate_queue_common(v.request, row.context, row.spatial_evidence)


@pytest.mark.parametrize(
    "offset,outcome", [(0, "SATISFIED"), (8, "SATISFIED"), (10, "NOT_SATISFIED")]
)
def test_candidate_beam_and_outside_retained_for_evaluation(offset, outcome):
    s, (a, p) = case(dec=20 + offset / 3600)
    assert p.outcome == outcome
    assert a.outcome == "SATISFIED"
    assert p.approval == a.approval == "APPROVED"
    assert p.method_version == "queue_pos_single_4"
    d = dict(p.derived)
    expected = math.degrees(1.13 * 299792458 / (338.5e9 * 12))
    assert d["candidate_fwhm_deg"] == pytest.approx(expected)
    assert d["candidate_radius_deg"] == expected / 2
    assert d["separation_deg"] * 3600 == pytest.approx(offset, abs=1e-8)
    assert s.total_retained == 1
    report = evaluate_candidate_search(s, queue_common=True)
    assert report.context_evaluations[0].criteria[:2] == (a, p)
    assert all(
        b.status == "INDETERMINATE" for b in report.context_evaluations[0].branches
    )


@pytest.mark.parametrize(
    "factor,outcome",
    [(1 - 1e-12, "SATISFIED"), (1, "SATISFIED"), (1 + 1e-12, "NOT_SATISFIED")],
)
def test_literal_boundary_without_legacy_equality_band(monkeypatch, factor, outcome):
    # Isolate numerical policy from inverse spherical coordinate rounding.
    radius = primary_beam_fwhm_deg(338.5, 12) / 2
    monkeypatch.setattr(
        "alma_duplicate.rules.queue_common._separation", lambda *a: radius * factor
    )
    _, (_, p) = case()
    assert p.outcome == outcome
    assert p.numeric_method == "SPHERICAL_FLOAT64_INCLUSIVE_NO_EQUALITY_BAND"


@pytest.mark.parametrize(
    "candidate,outcome",
    [
        ("0.45", "SATISFIED"),
        ("0.60", "SATISFIED"),
        ("0.6000001", "NOT_SATISFIED"),
        ("0.15", "SATISFIED"),
        ("0.1499999", "NOT_SATISFIED"),
    ],
)
def test_angular_symmetric_exact_limits(candidate, outcome):
    _, (a, p) = case({"Req. Ang. Res.": candidate})
    assert a.outcome == outcome
    assert a.candidate.semantics == "QUEUE_REQUESTED"
    assert a.candidate.source_field == "Req. Ang. Res."
    assert p.outcome == "SATISFIED"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"Use 7-m?": "True"}, "STANDALONE_ACA_EVIDENCE_UNAVAILABLE"),
        ({"Use TP?": "True"}, "TP_GEOMETRY_UNSUPPORTED"),
        ({"Mosaic": "Custom"}, "QUEUE_SINGLE_FIELD_REQUIRED"),
        ({"RA": "0", "Dec": "0"}, "QUEUE_CENTER_OR_FIXED_TARGET_UNRESOLVED"),
        ({"Mos. Coord.": "B1950"}, "QUEUE_POSITION_SCOPE_UNRESOLVED"),
    ],
)
def test_scope_never_becomes_definite_failure(changes, reason):
    _, rules = case(changes)
    assert all(r.outcome is None for r in rules)
    assert all(reason in r.reasons for r in rules)


def test_frequency_fallback_is_position_only():
    s, (_, p) = case({"Ref.Frequency": "0"})
    assert dict(p.details)["frequency_source"] == "sky_spw_weighted_mean"
    assert dict(p.derived)["candidate_frequency_ghz"] == pytest.approx(343.5)
    assert dict(p.details)["frequency_role"] == "POSITION_ONLY_NOT_CONT_FREQ"
    changed = replace(s.plan.validation.request, representative_frequency=None)
    r = s.queue.rows[0]
    p2 = evaluate_queue_common(changed, r.context, r.spatial_evidence)[1]
    assert (
        dict(p2.derived)["candidate_radius_deg"]
        == dict(p.derived)["candidate_radius_deg"]
    )
    report = evaluate_candidate_search(s, queue_common=True)
    assert (
        next(
            c
            for c in report.context_evaluations[0].criteria
            if c.criterion_id == "CONT-FREQ"
        ).outcome
        is None
    )


def test_missing_proposal_angular_does_not_erase_position():
    s, _ = case()
    r = s.queue.rows[0]
    a, p = evaluate_queue_common(
        replace(s.plan.validation.request, angular_resolution=None),
        r.context,
        r.spatial_evidence,
    )
    assert a.outcome is None and p.outcome == "SATISFIED"


def test_offsets_reuse_source_bound_spherical_profile():
    s, (_, p) = case({"Mosaic": "N/A", "Long Offset": "3", "Lat Offset": "4"})
    assert dict(p.derived)["separation_deg"] * 3600 == pytest.approx(5, abs=1e-8)
    assert "TANGENT_OFFSETS_SPHERICAL_1" in p.reasons
    assert s.queue.rows[0].context.evidence.row.spatial.long_offset_arcsec.value == 3


def test_context_and_snapshot_mismatches_rejected():
    s, _ = case()
    other, _ = case({"Target Name": "different"})
    r = s.queue.rows[0]
    o = other.queue.rows[0]
    with pytest.raises(ValueError, match="another context"):
        evaluate_queue_common(s.plan.validation.request, r.context, o.spatial_evidence)
    with pytest.raises(ValueError, match="another source result"):
        evaluate_queue_common(
            s.plan.validation.request,
            r.context,
            replace(r.spatial_evidence, source_record=o.spatial_evidence.source_record),
        )


def test_external_conflicting_interpretation_not_overwritten():
    from alma_duplicate.domain.spatial import PositionInterpretation

    s, _ = case()
    r = s.queue.rows[0]
    evidence = replace(
        r.spatial_evidence,
        interpretation=PositionInterpretation(
            r.context.context_id, "ICRS", "MOVING", "test"
        ),
    )
    assert all(
        c.outcome is None
        for c in evaluate_queue_common(s.plan.validation.request, r.context, evidence)
    )


def test_legacy_rule_keeps_provisional_boundary():
    from tests.integration.test_queue_candidate_beam import search

    s = search(dec=20 + 8.601107285572768 / 3600)
    r = s.queue.rows[0]
    old = evaluate_position_single(
        s.plan.validation.request, r.context, r.spatial_evidence
    )
    assert old.approval == "PROVISIONAL" and old.outcome is None
    assert "SPATIAL_BOUNDARY_TOLERANCE" in old.reasons


def test_archive_results_identical_when_queue_common_selected():
    v = validation(ra=10, dec=20)
    source, _ = archive(build_search_plan(v), s_ra=10.0, s_dec=20.0)
    s = search_candidates(
        v, archive_result=source, queue_result=queue_rows({"RA": "10", "Dec": "20"})
    )
    before = evaluate_candidate_search(s)
    after = evaluate_candidate_search(s, queue_common=True)
    assert before.context_evaluations[0] == after.context_evaluations[0]


def test_cli_all_retained_including_hidden_and_source_failure(tmp_path):
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--request",
                str(REQUEST),
                "--queue-csv",
                str(QUEUE),
                "--queue-common",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    scope = report["evaluation_scope"]
    assert scope["evaluated_contexts"] == scope["total_retained"] == 13
    assert scope["shown_candidates"] == 1
    assert all(
        c["criteria"][0]["method_version"] == "queue_angular_factor_5"
        for c in report["context_evaluations"]
    )
    assert all(
        c["criteria"][1]["method_version"] == "queue_pos_single_4"
        for c in report["context_evaluations"]
    )
    assert report["assessment"] == "NOT_AGGREGATED"
    assert (
        main(
            [
                "--request",
                str(REQUEST),
                "--queue-common",
                "--output",
                str(tmp_path / "missing.json"),
            ]
        )
        == 3
    )
    failed = json.loads((tmp_path / "missing.json").read_text())
    assert failed["sources"]["QUEUE"]["status"] == "NOT_PROVIDED"
    assert failed["assessment"] == "NOT_AGGREGATED"


def test_new_flag_requires_selected_queue(tmp_path):
    payload = json.loads(REQUEST.read_text())
    payload["search_options"]["sources"] = ["ARCHIVE"]
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload))
    assert (
        main(
            [
                "--request",
                str(path),
                "--queue-common",
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
        == 2
    )


def test_missing_beam_frequency_does_not_block_angular(monkeypatch):
    monkeypatch.setattr(
        "alma_duplicate.rules.queue_common.candidate_frequency",
        lambda row: (None, "Ref.Frequency", ("UNAVAILABLE",)),
    )
    _, (angular, position) = case()
    assert angular.outcome == "SATISFIED"
    assert position.outcome is None
    assert "CANDIDATE_FREQUENCY_UNAVAILABLE" in position.reasons


@pytest.mark.parametrize(
    "change", [dict(target_kind="MOVING"), dict(geometry="MOSAIC"), dict(position=None)]
)
def test_proposed_scope(change):
    s, _ = case()
    r = s.queue.rows[0]
    assert all(
        c.outcome is None
        for c in evaluate_queue_common(
            replace(s.plan.validation.request, **change), r.context, r.spatial_evidence
        )
    )


@pytest.mark.parametrize('use_7m', ['False', 'True'])
def test_tp_cannot_enter_interferometry_even_with_explicit_diameter(use_7m):
    from alma_duplicate.domain.spatial import PositionInterpretation
    s, _ = case({'Use 7-m?': use_7m, 'Use TP?': 'True'})
    r = s.queue.rows[0]
    evidence = replace(r.spatial_evidence, interpretation=PositionInterpretation(
        r.context.context_id, 'ICRS', 'FIXED', 'external-review', 12.0))
    rules = evaluate_queue_common(s.plan.validation.request, r.context, evidence)
    assert all(c.outcome is None and 'TP_GEOMETRY_UNSUPPORTED' in c.reasons for c in rules)
    assert dict(rules[1].derived)['antenna_diameter_m'] is None
    assert dict(rules[1].details)['array_scope'] == 'OUTSIDE_INTERFEROMETRY_SCOPE'


def test_7m_positive_flag_and_manual_diameter_do_not_prove_standalone():
    from alma_duplicate.domain.spatial import PositionInterpretation
    s, _ = case({'Use 7-m?': 'True', 'Use TP?': 'False'})
    r = s.queue.rows[0]
    evidence = replace(r.spatial_evidence, interpretation=PositionInterpretation(
        r.context.context_id, 'ICRS', 'FIXED', 'external-review', 7.0))
    rules = evaluate_queue_common(s.plan.validation.request, r.context, evidence)
    assert all(c.outcome is None and 'STANDALONE_ACA_EVIDENCE_UNAVAILABLE' in c.reasons for c in rules)
    assert dict(rules[1].derived)['antenna_diameter_m'] is None
    assert dict(rules[1].details)['array_scope'] == 'UNRESOLVED'


@pytest.mark.parametrize('flag,value', [('--queue-array', 'row=TP_ONLY'),
                                      ('--queue-array-decision-ref', 'review')])
def test_removed_cli_options_rejected_before_report(tmp_path, flag, value):
    output = tmp_path / 'report.json'
    with pytest.raises(SystemExit) as exc:
        main(['--request', str(REQUEST), '--queue-csv', str(QUEUE), '--queue-common',
              '--output', str(output), flag, value])
    assert exc.value.code == 2
    assert not output.exists()


def test_removed_api_does_not_silently_ignore_declarations():
    s, _ = case()
    with pytest.raises(TypeError, match='queue_array_declarations'):
        evaluate_candidate_search(s, queue_common=True, queue_array_declarations=())
    r = s.queue.rows[0]
    with pytest.raises(TypeError, match='array_declaration'):
        evaluate_queue_common(s.plan.validation.request, r.context, r.spatial_evidence,
                              array_declaration=None)
