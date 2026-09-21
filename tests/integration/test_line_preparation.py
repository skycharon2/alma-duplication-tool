"""Confirmed line evidence and pairing only; no numerical line verdicts."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_mode import derive_archive_mode
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.line_pairing import build_line_pairs
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.cli.evaluate import main
from tests.integration.test_search_plan_spatial import archive, queue
from alma_duplicate.search_plan import build_search_plan

ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "examples/confirmed_line"


def payload():
    return json.loads((EXAMPLE / "request.json").read_text())


def validate(p=None):
    p = payload() if p is None else p
    return validate_proposed_observation(p["request"], p["search_options"])


def planned(p=None):
    v = validate(p)
    assert v.is_valid, v.issues
    r = v.request
    return prepare_line_window(
        r.spectral_windows[0], r.sensitivities, r.source_redshift
    )


def report(p=None):
    return evaluate_candidate_search(
        search_candidates(
            validate(p),
            archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json"),
        )
    )


@pytest.mark.parametrize("z", [0, -0.5, 0.024, 1e5])
def test_rest_redshift_is_explicit(z):
    p = payload()
    p["request"]["source_redshift"] = z
    assert planned(p).sky_frequency_ghz == pytest.approx(230.538 / (1 + z))


@pytest.mark.parametrize("z", [-1, -2, True, float("nan"), float("inf"), "n/a"])
def test_invalid_redshift_rejected_even_unselected(z):
    p = payload()
    p["request"].update(source_redshift=z, intents=["CONTINUUM"])
    v = validate(p)
    assert not v.is_valid and any(i.path == "request.source_redshift" for i in v.errors)


def test_rest_requires_redshift_sky_does_not_and_no_representative_fallback():
    p = payload()
    p["request"].pop("source_redshift")
    p["request"]["representative_frequency"] = {
        "value": 100,
        "unit": "GHz",
        "kind": "SKY",
    }
    r = planned(p)
    assert r.sky_frequency_ghz is None and "SOURCE_REDSHIFT_REQUIRED" in r.reasons
    assert validate(p).can_search
    p["request"]["spectral_windows"][0]["center"]["kind"] = "SKY"
    assert planned(p).sky_frequency_ghz == 230.538


@pytest.mark.parametrize(
    "location,quantity",
    [
        ("smoothing", {"value": 20000, "unit": "m/s"}),
        ("window", {"value": 20, "unit": "km/s"}),
        ("window", {"value": 15, "unit": "MHz"}),
        ("window", {"value": 15000, "unit": "kHz"}),
    ],
)
def test_planned_resolution_reuses_existing_fields(location, quantity):
    p = payload()
    p["request"]["sensitivities"][0].pop("smoothing_resolution")
    if location == "smoothing":
        p["request"]["sensitivities"][0]["smoothing_resolution"] = quantity
    else:
        p["request"]["spectral_windows"][0]["spectral_resolution"] = quantity
    expected = (
        20
        if quantity["unit"] in {"m/s", "km/s"}
        else 299792.458 * 0.015 / 225.134765625
    )
    assert planned(p).planned_resolution_kms == pytest.approx(expected)


def test_resolution_conflict_has_no_selected_value_or_spacing_fallback():
    p = payload()
    w = p["request"]["spectral_windows"][0]
    w["spectral_resolution"] = {"value": 20, "unit": "km/s"}
    assert planned(p).planned_resolution_kms == 20
    w["spectral_resolution"]["value"] = 19
    assert planned(p).planned_resolution_kms is None
    assert "CONFLICTING_PLANNED_RESOLUTIONS" in planned(p).reasons
    assert any(i.code == "CONFLICTING_PLANNED_RESOLUTIONS" for i in validate(p).issues)
    w.pop("spectral_resolution")
    p["request"]["sensitivities"][0].pop("smoothing_resolution")
    w["channel_spacing"] = {"value": 100, "unit": "kHz"}
    assert planned(p).planned_resolution_kms is None
    assert "PLANNED_RESOLUTION_REQUIRED" in planned(p).reasons


def test_missing_frequency_blocks_mhz_resolution_and_overflow_stays_unknown():
    p = payload()
    p["request"].pop("source_redshift")
    p["request"]["spectral_windows"][0]["spectral_resolution"] = {
        "value": 1,
        "unit": "MHz",
    }
    assert planned(p).planned_resolution_kms is None
    p = payload()
    p["request"]["source_redshift"] = -0.9999999999999999
    p["request"]["spectral_windows"][0]["center"]["value"] = 1e308
    assert "SKY_FREQUENCY_UNREPRESENTABLE" in planned(p).reasons


def mode_input():
    source, context = archive(build_search_plan(validate()))
    return source, context.evidence.row_link.association_key


@pytest.mark.parametrize(
    "raw,expected",
    [
        (1, "TDM"),
        (128, "TDM"),
        (129, "FDM"),
        (1920, "FDM"),
        (np.int64(129), "FDM"),
        (None, "UNKNOWN"),
        (np.ma.masked, "UNKNOWN"),
        (True, "UNKNOWN"),
        (np.bool_(True), "UNKNOWN"),
        (0, "UNKNOWN"),
        (-1, "UNKNOWN"),
        (128.5, "UNKNOWN"),
        (128.0, "UNKNOWN"),
        ("129", "UNKNOWN"),
        (float("inf"), "UNKNOWN"),
    ],
)
def test_versioned_mode_is_integer_metadata_derived(raw, expected):
    source, association = mode_input()
    mode = derive_archive_mode(
        source.provenance.query_run_id,
        association,
        [("row", raw)],
        source.field_metadata,
    )
    assert mode.operational_mode == expected
    assert mode.evidence_level == "DERIVED" and mode.decision_ref
    assert mode.observations[0].raw_row_id == "row"


@pytest.mark.parametrize("change", ["missing", "duplicate", "double", "unit", "array"])
def test_bad_mode_metadata_blocks_classification(change):
    source, association = mode_input()
    fields = source.field_metadata
    field = next(f for f in fields if f.name == "em_xel")
    if change == "missing":
        fields = tuple(f for f in fields if f.name != "em_xel")
    elif change == "duplicate":
        fields = (*fields, field)
    else:
        replacement = replace(
            field,
            **{
                "double": {"datatype": "double"},
                "unit": {"unit": "GHz"},
                "array": {"arraysize": "2"},
            }[change],
        )
        fields = tuple(replacement if f.name == "em_xel" else f for f in fields)
    mode = derive_archive_mode("run", association, [("row", 129)], fields)
    assert mode.status == "UNKNOWN" and mode.ui_type == "UNKNOWN"


@pytest.mark.parametrize("other_count", [128, 2048, None])
def test_same_association_conflict_is_retained_before_pairing(other_count):
    source, context = archive(build_search_plan(validate()), em_xel=1920)
    other = dict(source.rows[0], em_xel=other_count)
    source = replace(source, rows=(source.rows[0], other))
    contexts = build_archive_contexts(source).contexts
    assert len(contexts) == 2
    for c in contexts:
        m = c.evidence.mode_evidence
        assert m.status == "UNKNOWN" and len(m.observations) == 2
        attempt = build_line_pairs(validate().request, c).attempts[0]
        assert attempt.reference is None
        assert "CONFLICTING_CONTEXT_ALTERNATIVES" in attempt.reasons


def test_distinct_spws_and_executions_do_not_pool_mode_counts():
    source, _ = archive(build_search_plan(validate()), em_xel=1920)
    original = source.rows[0]
    variants = [
        dict(
            original,
            em_xel=128,
            obs_id=str(original["obs_id"]).replace(".spw.0", ".spw.1"),
        ),
        dict(original, em_xel=128, asdm_uid="uid://A002/Xdifferent/X1"),
    ]
    for other in variants:
        contexts = build_archive_contexts(
            replace(source, rows=(original, other))
        ).contexts
        assert len(contexts) == 2
        assert [c.evidence.mode_evidence.operational_mode for c in contexts] == [
            "FDM",
            "TDM",
        ]
        assert all(len(c.evidence.mode_evidence.observations) == 1 for c in contexts)


def test_cli_guide_b_prepares_both_pairs_and_evaluates_line_without_filtering_pairs(
    tmp_path, monkeypatch
):
    import requests

    monkeypatch.setattr(
        requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network")
    )
    out = tmp_path / "report.json"
    assert (
        main(
            [
                "--request",
                str(EXAMPLE / "request.json"),
                "--archive-replay",
                str(EXAMPLE / "archive/manifest.json"),
                "--output",
                str(out),
            ]
        )
        == 0
    )
    doc = json.loads(out.read_text())
    assert doc["evaluation_version"] == "5"
    assert doc["request"]["normalized"]["model_version"] == "2"
    assert doc["evaluation_scope"]["shown_candidates"] == 1
    assert doc["evaluation_scope"]["evaluated_contexts"] == 2
    for row, mode in zip(doc["context_evaluations"], ["FDM", "TDM"]):
        pairing = row["line_pairing"]
        assert pairing["assessment"] == "NOT_EVALUATED"
        a = pairing["attempts"][0]
        assert a["association_status"] == "RESOLVED" and a["reference"]
        assert a["candidate_mode"]["operational_mode"] == mode
        assert a["proposed"]["sky_frequency_ghz"] == 225.134765625
        assert a["proposed"]["planned_resolution_kms"] == 20
        assert row["branches"][0]["status"] == ("CRITERIA_MET" if mode == "FDM" else "CRITERIA_NOT_MET")
    assert doc["assessment"] == "NOT_AGGREGATED"


def test_multiple_windows_never_borrow_rms_and_unselected_has_no_pairs():
    p = payload()
    p["request"]["spectral_windows"].append(
        dict(p["request"]["spectral_windows"][0], window_id="line-1")
    )
    pairs = report(p).context_evaluations[0].line_pairing.attempts
    assert len(pairs) == 2 and pairs[0].reference is not None
    assert (
        pairs[1].reference is None
        and "UNIQUE_WINDOW_LINE_SENSITIVITY_REQUIRED" in pairs[1].reasons
    )
    s = deepcopy(p["request"]["sensitivities"][0])
    s["sensitivity_id"] = "ambiguous"
    p["request"]["sensitivities"].append(s)
    assert report(p).context_evaluations[0].line_pairing.attempts[0].reference is None
    p["request"]["intents"] = ["CONTINUUM"]
    assert all(c.line_pairing is None for c in report(p).context_evaluations)


def test_pair_resolve_rejects_cross_context_spw_and_mode_origin():
    r = report()
    request = r.search_result.plan.validation.request
    first, second = r.context_evaluations
    pair = first.line_pairing.attempts[0].reference
    assert pair.resolve(request, first.candidate.context)[2].resolution.value == 500
    with pytest.raises(ValueError):
        pair.resolve(request, second.candidate.context)
    c = first.candidate.context
    bad = replace(
        c,
        evidence=replace(
            c.evidence, mode_evidence=second.candidate.context.evidence.mode_evidence
        ),
    )
    with pytest.raises(ValueError, match="Mode evidence"):
        build_line_pairs(request, bad)
    invalid_rms = replace(request.sensitivities[0], setup_id="another-setup")
    with pytest.raises(ValueError):
        pair.resolve(replace(request, sensitivities=(invalid_rms,)), c)


def test_queue_unsupported_missing_and_unknown_are_not_negative():
    _, c = queue()
    a = build_line_pairs(validate().request, c).attempts[0]
    assert a.association_status == "UNSUPPORTED" and a.reference is None
    p = payload()
    p["request"]["spectral_windows"] = []
    p["request"]["sensitivities"] = []
    empty = report(p).context_evaluations[0].line_pairing
    assert empty.assessment == "NOT_EVALUATED" and empty.reasons == (
        "NO_PROPOSED_LINE_WINDOWS",
    )


def test_source_failure_yields_no_fabricated_pairs():
    r = evaluate_candidate_search(search_candidates(validate()))
    assert not r.context_evaluations and r.assessment == "NOT_AGGREGATED"


@pytest.mark.parametrize(
    "raw", [None, np.ma.masked, np.bool_(True), float("nan"), float("inf"), 1j, b"129"]
)
def test_invalid_mode_values_remain_serializable_evidence(raw):
    from alma_duplicate.reporting import json_value

    source, association = mode_input()
    mode = derive_archive_mode(
        "run", association, [("row", raw)], source.field_metadata
    )
    assert mode.operational_mode == "UNKNOWN"
    json.dumps(json_value(mode), allow_nan=False)


def test_mixed_resolution_units_can_agree_exactly():
    p = payload()
    p["request"]["source_redshift"] = 0
    w = p["request"]["spectral_windows"][0]
    w["center"]["value"] = 299792.458
    w["spectral_resolution"] = {"value": 20000, "unit": "MHz"}
    assert planned(p).planned_resolution_kms == 20
    assert "CONFLICTING_PLANNED_RESOLUTIONS" not in planned(p).reasons


def test_missing_mode_keeps_resolved_pair_and_missing_rms_is_not_borrowed():
    v = validate()
    source, _ = archive(build_search_plan(v), em_xel=None)
    r = evaluate_candidate_search(search_candidates(v, archive_result=source))
    a = r.context_evaluations[0].line_pairing.attempts[0]
    assert a.reference is not None and a.evidence_status == "INCOMPLETE"
    assert a.candidate_mode.operational_mode == "UNKNOWN"
    assert "MISSING_COUNT" in a.reasons
    p = payload()
    p["request"]["sensitivities"][0].pop("rms")
    a = report(p).context_evaluations[0].line_pairing.attempts[0]
    assert "PLANNED_LINE_RMS_REQUIRED" in a.reasons and a.reference is not None


def test_mixed_intents_keep_pair_preparation_and_branches_separate():
    p = payload()
    p["request"]["intents"] = ["CONTINUUM", "LINE"]
    r = report(p)
    for c in r.context_evaluations:
        assert c.line_pairing is not None
        assert [b.branch for b in c.branches] == ["CONTINUUM", "LINE"]
        assert c.branches[1].status == ("CRITERIA_MET" if c.line_pairing.attempts[0].candidate_mode.operational_mode == "FDM" else "CRITERIA_NOT_MET")


def test_pair_result_enforces_context_and_window_identity():
    r = report()
    first, second = r.context_evaluations
    a = first.line_pairing.attempts[0]
    with pytest.raises(ValueError):
        replace(a, proposed_window_id="another")
    with pytest.raises(ValueError):
        replace(first.line_pairing, attempts=(a, a))
    with pytest.raises(ValueError):
        replace(first, line_pairing=second.line_pairing)


def test_no_source_reads_for_solar_with_valid_line_inputs(tmp_path, monkeypatch):
    import alma_duplicate.cli.evaluate as cli

    monkeypatch.setattr(cli, "search_candidates", lambda *a, **k: pytest.fail("search"))
    p = payload()
    p["request"]["target_kind"] = "SUN"
    request = tmp_path / "solar.json"
    request.write_text(json.dumps(p))
    out = tmp_path / "out.json"
    assert (
        main(
            [
                "--request",
                str(request),
                "--archive-replay",
                "nonexistent.json",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    assert json.loads(out.read_text())["report_kind"] == "SOLAR_EXEMPTION"
