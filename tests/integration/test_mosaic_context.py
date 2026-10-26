from dataclasses import replace
from types import SimpleNamespace
import pytest
from tests.integration.test_context_rule_evaluation import sample
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from alma_duplicate.proposed_mosaic import import_proposed


def as_mosaic_context(context):
    prepared = context.evidence.prepared
    normalized = prepared.normalized_metadata
    return replace(context, evidence=replace(context.evidence, prepared=replace(prepared,
        raw_row=dict(prepared.raw_row, is_mosaic='T'),
        normalized_metadata=replace(normalized, is_mosaic=replace(normalized.is_mosaic, value=True)))))


def data():
    search = sample()
    context = as_mosaic_context(search.archive.retained_rows[0].context)
    request = replace(
        search.plan.validation.request, geometry="MOSAIC", target_name="proposed"
    )
    proposed = import_proposed(
        b"RA,Dec,Coordinate Type,Coordinate Units\n--\n0,0,Absolute,Degrees\n",
        source_name="proposed",
        array="12m",
        confirm_fixed_icrs=True,
        confirm_complete=True,
    )
    raw = context.evidence.prepared.raw_row
    execution = dict(
        member_ous_uid=raw["member_ous_uid"],
        source_name=raw["target_name"],
        asdm_uid=raw["asdm_uid"],
        evidence=dict(fields=[dict(field_id=1, frame="ICRS", ra_deg=0.0, dec_deg=0.0)]),
    )
    array = SimpleNamespace(
        context_id=context.context_id,
        source_record_id=context.reference.source_record_id,
        diameters_m=(12.0,),
    )
    return request, context, proposed, execution, array


def test_archive_metadata_not_listobs_spws_and_shared_rules():
    request, context, proposed, execution, array = data()
    r = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert (
        r["coverage"]["frequency_ghz"]
        == context.evidence.prepared.comparison_evidence.frequency.centre.canonical_value
    )
    assert (
        next(c for c in r["criteria"] if c.criterion_id == "POS-MOSAIC").outcome
        == "SATISFIED"
    )
    assert {"ANGULAR", "CONT-FREQ", "CONT-RMS"} <= {
        c.criterion_id for c in r["criteria"]
    }
    assert "POS-MOSAIC" in r["branches"][0].required_criteria
    from alma_duplicate.rules.continuum import (
        evaluate_continuum_frequency,
        evaluate_continuum_rms,
    )

    assert r["criteria"][2] == evaluate_continuum_frequency(request, context)
    assert r["criteria"][3] == evaluate_continuum_rms(request, context)


def test_missing_pointings_still_evaluates_other_conditions():
    request, context, proposed, _, array = data()
    r = evaluate_mosaic_context(request, context, proposed, array_evidence=array)
    assert r["criteria"][1].outcome is None
    assert len(r["criteria"]) == 4


def test_identity_conflict_and_different_execution():
    request, context, proposed, execution, array = data()
    execution["member_ous_uid"] = "wrong"
    with pytest.raises(ValueError):
        evaluate_mosaic_context(
            request, context, proposed, executions=[execution], array_evidence=array
        )
    request, context, proposed, execution, array = data()
    execution["asdm_uid"] = "other"
    assert (
        evaluate_mosaic_context(
            request, context, proposed, executions=[execution], array_evidence=array
        )["coverage"]
        is None
    )


def test_line_uses_mosaic_position_without_relabeling_request():
    request, context, proposed, execution, array = data()
    request = replace(request, intents=("LINE",))
    r = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert "POS-MOSAIC" in r["branches"][0].required_criteria
    assert "FIXED_SINGLE_POINT_REQUEST_REQUIRED" not in r["line_pairing"].reasons


def test_assessment_entrypoint_preserves_context_and_no_geometry_spw_requirements(
    monkeypatch,
):
    from alma_duplicate.assessment import assess_archive_mosaic_contexts
    import alma_duplicate.archive_mosaic_pointings as loader

    request, context, proposed, execution, array = data()
    calls = []

    def load(path):
        calls.append(path)
        return [execution], {}

    monkeypatch.setattr(loader, "load_package_executions", load)
    raw = context.evidence.prepared.raw_row
    report = assess_archive_mosaic_contexts(
        request,
        proposed,
        [context],
        package_directories={
            (raw["member_ous_uid"], raw["target_name"]): "/verified/package"
        },
        array_catalog=SimpleNamespace(bind=lambda c: array),
    )
    assert len(calls) == 1
    assert report["contexts"][0]["criteria"][1]["outcome"] == "SATISFIED"
    assert report["contexts"][0]["branches"][0]["required_criteria"][0] == "POS-MOSAIC"


def other_execution(context, execution, *, ra=1.0, frequency=None):
    from copy import deepcopy

    raw = dict(context.evidence.prepared.raw_row)
    raw["asdm_uid"] = "uid://A002/Xother/X1"
    if frequency is not None:
        # Different normalized frequency must prevent union even with matching labels.
        evidence = context.evidence.prepared.comparison_evidence
        q = replace(evidence.frequency.centre, canonical_value=frequency)
        comparison = replace(evidence, frequency=replace(evidence.frequency, centre=q))
    else:
        comparison = context.evidence.prepared.comparison_evidence
    prepared = replace(
        context.evidence.prepared, raw_row=raw, comparison_evidence=comparison
    )
    other = replace(
        context,
        context_id="other",
        evidence=replace(context.evidence, prepared=prepared),
    )
    e = deepcopy(execution)
    e["asdm_uid"] = raw["asdm_uid"]
    e["evidence"]["fields"][0]["ra_deg"] = ra
    return other, e


def test_multi_execution_union_counts_proposed_rows_once():
    request, context, proposed, execution, array = data()
    other, second = other_execution(context, execution)
    proposed = dict(
        proposed,
        points=[
            dict(id=str(i), frame="ICRS", ra_deg=ra, dec_deg=0.0)
            for i, ra in enumerate((0.0, 1.0, 2.0))
        ],
    )
    alone = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert alone["criteria"][1].outcome is None
    result = evaluate_mosaic_context(
        request,
        context,
        proposed,
        executions=[execution, second],
        array_evidence=array,
        metadata_contexts=[context, other],
    )
    assert result["coverage"]["inside_count"] == 2
    assert result["criteria"][1].outcome == "SATISFIED"
    assert len(result["coverage"]["included_asdm_uids"]) == 2
    other, second = other_execution(context, execution, ra=0.0)
    duplicate = evaluate_mosaic_context(
        request,
        context,
        proposed,
        executions=[execution, second],
        array_evidence=array,
        metadata_contexts=[other],
    )
    assert duplicate["coverage"]["inside_count"] == 1


def test_incompatible_metadata_cannot_expand_coverage():
    request, context, proposed, execution, array = data()
    other, second = other_execution(context, execution, frequency=999.0)
    result = evaluate_mosaic_context(
        request,
        context,
        proposed,
        executions=[execution, second],
        array_evidence=array,
        metadata_contexts=[other],
    )
    assert len(result["coverage"]["included_asdm_uids"]) == 1
    assert (
        result["coverage"]["excluded_executions"][0]["asdm_uid"] == second["asdm_uid"]
    )


@pytest.mark.parametrize(
    "complete,ra,reason",
    [
        (False, 0.0, "PROPOSED_POINTING_COMPLETENESS_REQUIRED"),
        (True, 1.0, "ARCHIVE_MEMBER_COMPLETENESS_REQUIRED_FOR_NEGATIVE_RESULT"),
    ],
)
def test_coverage_failure_has_precise_issue(complete, ra, reason):
    request, context, proposed, execution, array = data()
    proposed = dict(
        proposed,
        completeness="USER_CONFIRMED_COMPLETE" if complete else "NOT_CONFIRMED",
        points=[dict(id="0", frame="ICRS", ra_deg=ra, dec_deg=0.0)],
    )
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    criterion = result["criteria"][1]
    assert criterion.reasons == (reason,)
    assert criterion.issues[0].code == reason


def test_exact_half_and_boundary_are_not_positive():
    request, context, proposed, execution, array = data()
    proposed = dict(
        proposed,
        points=[
            dict(id="0", frame="ICRS", ra_deg=0.0, dec_deg=0.0),
            dict(id="1", frame="ICRS", ra_deg=1.0, dec_deg=0.0),
        ],
    )
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert result["coverage"]["inside_count"] == 1
    assert result["criteria"][1].outcome is None
    radius = result["coverage"]["circles"][0]["radius_arcsec"]
    proposed = dict(
        proposed,
        points=[dict(id="boundary", frame="ICRS", ra_deg=radius / 3600.0, dec_deg=0.0)],
    )
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert result["criteria"][1].issues[0].code == "MOSAIC_BOUNDARY_COUNT_UNRESOLVED"


def test_unready_execution_keeps_its_actual_exclusion_reason():
    request, context, proposed, execution, array = data()
    result = evaluate_mosaic_context(
        request,
        context,
        proposed,
        executions=[execution],
        array_evidence=array,
        ready_asdm_uids=set(),
    )
    position = result["criteria"][1]
    assert position.issues[0].code == "EXECUTION_POSITION_READINESS_REQUIRED"
    assert (
        dict(position.details)["excluded_executions"][0]["asdm_uid"]
        == execution["asdm_uid"]
    )
