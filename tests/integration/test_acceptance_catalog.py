"""Pinned inputs, independent expectations and report-consumer semantics."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import requests

from alma_duplicate.cli.acceptance import (
    main,
    load_catalog,
    run_catalog,
    compare_assertions,
    _effective_evaluation_configuration,
    _evaluation_flags,
)
from alma_duplicate.report_inspection import inspect_report

ROOT = Path(__file__).parents[2]
CATALOG = ROOT / "examples/acceptance/catalog.json"

FALSE_EVALUATION_OPTIONS = {
    "queue_common": False,
    "queue_continuum": False,
    "queue_line": False,
}

FALSE_EVALUATION_CONFIGURATION = {
    "nominal_conversion": None,
    "queue_common": False,
    "queue_continuum": False,
    "queue_line": False,
}

DUAL_SOURCE_CONTINUUM_OPTIONS = {
    "queue_common": False,
    "queue_continuum": True,
    "queue_line": False,
}

DUAL_SOURCE_CONTINUUM_CONFIGURATION = {
    "nominal_conversion": None,
    "queue_common": True,
    "queue_continuum": True,
    "queue_line": False,
}


@pytest.fixture(scope="module")
def accepted(tmp_path_factory):
    output = tmp_path_factory.mktemp("acceptance") / "run"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            requests.sessions.Session,
            "request",
            lambda *a, **k: pytest.fail("network access"),
        )
        result = run_catalog(CATALOG, output)
    return output, result


def report(accepted, case):
    return json.loads((accepted[0] / case / "report.json").read_text())


def one_case(tmp_path, case_id="guide-b"):
    catalog = json.loads(CATALOG.read_text())
    case = next(c for c in catalog["cases"] if c["case_id"] == case_id)
    for item in case["inputs"].values():
        item["path"] = str((CATALOG.parent / item["path"]).resolve())
    catalog["cases"] = [case]
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog))
    return path, catalog


def test_all_cases_pass_without_claiming_scientific_review(accepted):
    output, result = accepted
    assert result["status"] == "PASS" and len(result["cases"]) == 10
    assert result["acceptance_run_version"] == "2"
    assert result["catalog_version"] == "2"
    assert result["scientific_review_inferred_from_test_pass"] is False
    assert result["reviewed_real_proposal_cases"] == 0
    for c in result["cases"]:
        assert c["review"]["status"] == "AWAITING_INDEPENDENT_REVIEW"
        assert c["review"]["reviewer"] is None
        expected_options = (
            DUAL_SOURCE_CONTINUUM_OPTIONS
            if c["case_id"] == "dual-source-continuum"
            else FALSE_EVALUATION_OPTIONS
        )
        expected_configuration = (
            DUAL_SOURCE_CONTINUUM_CONFIGURATION
            if c["case_id"] == "dual-source-continuum"
            else FALSE_EVALUATION_CONFIGURATION
        )
        assert c["evaluation_options"] == expected_options
        assert c["differences"] == []
        assert (
            report(accepted, c["case_id"])["evaluation_configuration"]
            == expected_configuration
        )
        assert (output / c["case_id"] / "inspection.json").is_file()
        assert (output / c["case_id"] / "comparison.json").is_file()
    diagnostic = report(accepted, "ngc6240-line-diagnostic")
    assert diagnostic["request"]["normalized"]["angular_resolution"]["value"] == 0.5


def test_catalog_v1_remains_readable_with_historical_option_semantics(
    tmp_path,
):
    path, catalog = one_case(tmp_path)

    catalog["catalog_version"] = "1"
    catalog["cases"][0].pop(
        "evaluation_options"
    )
    catalog["cases"][0].pop(
        "queue_candidate_beam"
    )
    path.write_text(
        json.dumps(catalog)
    )

    loaded_catalog, loaded = load_catalog(
        path
    )

    assert (
        loaded_catalog["catalog_version"]
        == "1"
    )
    assert (
        loaded[0][2]
        == FALSE_EVALUATION_OPTIONS
    )


@pytest.mark.parametrize(
    ("options", "flags", "effective"),
    [
        (
            {
                "queue_common": False,
                "queue_continuum": False,
                "queue_line": False,
            },
            (),
            {
                "nominal_conversion": None,
                "queue_common": False,
                "queue_continuum": False,
                "queue_line": False,
            },
        ),
        (
            {
                "queue_common": True,
                "queue_continuum": False,
                "queue_line": False,
            },
            ("--queue-common",),
            {
                "nominal_conversion": None,
                "queue_common": True,
                "queue_continuum": False,
                "queue_line": False,
            },
        ),
        (
            {
                "queue_common": False,
                "queue_continuum": True,
                "queue_line": False,
            },
            ("--queue-continuum",),
            {
                "nominal_conversion": None,
                "queue_common": True,
                "queue_continuum": True,
                "queue_line": False,
            },
        ),
        (
            {
                "queue_common": False,
                "queue_continuum": False,
                "queue_line": True,
            },
            ("--queue-line",),
            {
                "nominal_conversion": None,
                "queue_common": True,
                "queue_continuum": False,
                "queue_line": True,
            },
        ),
        (
            {
                "queue_common": True,
                "queue_continuum": True,
                "queue_line": True,
            },
            (
                "--queue-common",
                "--queue-continuum",
                "--queue-line",
            ),
            {
                "nominal_conversion": None,
                "queue_common": True,
                "queue_continuum": True,
                "queue_line": True,
            },
        ),
    ],
)
def test_evaluation_options_have_deterministic_cli_and_effective_mapping(
    options,
    flags,
    effective,
):
    assert (
        _evaluation_flags(options)
        == flags
    )
    assert (
        _effective_evaluation_configuration(
            options
        )
        == effective
    )


def test_v2_runner_records_line_selection_when_queue_is_not_provided(
    tmp_path,
):
    path, catalog = one_case(
        tmp_path,
        "source-not-provided",
    )

    catalog["cases"][0][
        "evaluation_options"
    ]["queue_line"] = True

    path.write_text(
        json.dumps(catalog)
    )

    output = tmp_path / "run"

    result = run_catalog(
        path,
        output,
    )

    assert result["status"] == "PASS"

    case = result["cases"][0]

    assert case["exit_code"] == 3
    assert case["evaluation_options"] == {
        "queue_common": False,
        "queue_continuum": False,
        "queue_line": True,
    }

    document = json.loads(
        (
            output
            / "source-not-provided"
            / "report.json"
        ).read_text()
    )

    assert (
        document["sources"]["QUEUE"]["status"]
        == "NOT_PROVIDED"
    )

    assert document[
        "evaluation_configuration"
    ] == {
        "nominal_conversion": None,
        "queue_common": True,
        "queue_continuum": False,
        "queue_line": True,
    }


@pytest.mark.parametrize(
    "change",
    [
        "missing-options",
        "missing-option-key",
        "unknown-option",
        "non-boolean-option",
        "unknown-case-key",
        "non-boolean-queue-candidate-beam",
    ],
)
def test_catalog_v2_rejects_ambiguous_evaluation_schema(
    tmp_path,
    change,
):
    path, catalog = one_case(
        tmp_path
    )

    case = catalog["cases"][0]

    if change == "missing-options":
        case.pop(
            "evaluation_options"
        )

    elif change == "missing-option-key":
        case[
            "evaluation_options"
        ].pop(
            "queue_line"
        )

    elif change == "unknown-option":
        case[
            "evaluation_options"
        ][
            "queue_lnie"
        ] = True

    elif change == "non-boolean-option":
        case[
            "evaluation_options"
        ][
            "queue_line"
        ] = "true"

    elif change == "unknown-case-key":
        case[
            "evaluation_option"
        ] = {}

    else:
        case[
            "queue_candidate_beam"
        ] = "false"

    path.write_text(
        json.dumps(catalog)
    )

    with pytest.raises(
        ValueError
    ):
        load_catalog(path)


@pytest.mark.parametrize(
    ("case_id", "option", "message"),
    [
        (
            "guide-b",
            "queue_common",
            "QUEUE source selection",
        ),
        (
            "source-not-provided",
            "queue_continuum",
            "CONTINUUM intent",
        ),
        (
            "ngc6240-continuum",
            "queue_line",
            "LINE intent",
        ),
    ],
)
def test_catalog_v2_rejects_options_outside_request_contract(
    tmp_path,
    case_id,
    option,
    message,
):
    path, catalog = one_case(
        tmp_path,
        case_id,
    )

    catalog["cases"][0][
        "evaluation_options"
    ][option] = True

    path.write_text(
        json.dumps(catalog)
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        load_catalog(path)


def test_report_consumer_never_changes_evaluator_report_or_top_level_assessment(
    accepted,
):
    doc = report(accepted, "mixed-intents")
    original = deepcopy(doc)
    view = inspect_report(doc)
    assert doc == original
    assert view["assessment"] == "NOT_AGGREGATED"
    assert view["search_wide_verdict"] == "NOT_PROVIDED"
    assert view["scope"]["evaluated_contexts"] == 2
    assert view["scope"]["shown_candidates"] == 1
    assert sum(c["count"] for c in view["branch_counts"]) == 4


def test_missing_input_candidate_missing_and_dependency_remain_distinct(accepted):
    missing = inspect_report(report(accepted, "missing-line-rms"))
    assert any(
        o["category"] == "USER_INPUT_MISSING"
        and o["code"] == "PLANNED_LINE_RMS_REQUIRED"
        for o in missing["gap_occurrences"]
    )
    candidate = inspect_report(report(accepted, "guide-a"))
    assert any(
        o["category"] == "ARCHIVE_EVIDENCE_MISSING"
        for o in candidate["gap_occurrences"]
    )
    coarse = inspect_report(report(accepted, "coarse-line-resolution"))
    assert any(
        o["category"] == "METHOD_OR_DEPENDENCY"
        and o["code"] == "ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED"
        for o in coarse["gap_occurrences"]
    )


def test_shared_common_conditions_not_counted_again_in_each_pair(accepted):
    doc = report(accepted, "multiple-line-windows")
    common = doc["context_evaluations"][0]["criteria"][0]
    common.update(approval="PROVISIONAL")
    for pair in doc["context_evaluations"][0]["line_pairs"]:
        for q in pair["criteria"]:
            if q["criterion_id"] == "ANGULAR":
                q.update(approval="PROVISIONAL")
    gaps = inspect_report(doc)["gap_occurrences"]
    assert sum(o["code"] == "METHOD_UNAPPROVED" for o in gaps) == 1


def test_source_failure_preserves_successful_archive_results(accepted):
    view = inspect_report(report(accepted, "source-not-provided"))
    assert view["source_statuses"]["QUEUE"] == "NOT_PROVIDED"
    assert view["branch_counts"] and view["search_wide_verdict"] == "NOT_PROVIDED"
    assert any(
        o["code"] == "NOT_PROVIDED" and o["category"] == "SOURCE_OR_SEARCH_INCOMPLETE"
        for o in view["gap_occurrences"]
    )
    case = next(
        c for c in accepted[1]["cases"] if c["case_id"] == "source-not-provided"
    )
    assert case["status"] == "PASS" and case["exit_code"] == 3


def test_real_mapping_scope_and_association_categories_are_explicit(accepted):
    gaps = inspect_report(report(accepted, "ngc6240-line-diagnostic"))[
        "gap_occurrences"
    ]
    assert any(o["category"] == "ASSOCIATION_UNRESOLVED" for o in gaps)
    assert any(
        o["category"] == "SCOPE_UNSUPPORTED" and o["source"] == "QUEUE" for o in gaps
    )


def test_future_reason_is_unclassified_not_invented_input_requirement(accepted):
    doc = report(accepted, "guide-b")
    r = doc["context_evaluations"][0]["line_pairs"][0]["criteria"][-1]
    r.update(
        outcome=None,
        evaluation="INSUFFICIENT_INFORMATION",
        issues=[],
        reasons=["NEW_REASON"],
    )
    gaps = inspect_report(doc)["gap_occurrences"]
    assert (
        next(o for o in gaps if o["code"] == "NEW_REASON")["category"] == "UNCLASSIFIED"
    )


def test_empty_search_is_not_absence_and_unknown_version_is_rejected(accepted):
    doc = report(accepted, "guide-b")
    doc["context_evaluations"] = []
    doc["evaluation_scope"].update(
        evaluated_contexts=0, total_retained=0, shown_candidates=0
    )
    view = inspect_report(doc)
    assert view["branch_counts"] == [] and view["search_wide_verdict"] == "NOT_PROVIDED"
    doc["report_version"] = "99"
    with pytest.raises(ValueError, match="version 4"):
        inspect_report(doc)


def test_solar_no_query_is_not_incomplete_source():
    from alma_duplicate.rules.evaluation_model import SolarExemptionReport
    from alma_duplicate.request_validation import validate_proposed_observation
    from alma_duplicate.reporting import report_document

    payload = json.loads((ROOT / "examples/confirmed_line/request.json").read_text())
    payload["request"]["target_kind"] = "SUN"
    doc = report_document(
        SolarExemptionReport(
            validation=validate_proposed_observation(
                payload["request"], payload["search_options"]
            )
        )
    )
    view = inspect_report(doc)
    assert view["report_kind"] == "SOLAR_EXEMPTION"
    assert view["assessment"] == "NOT_APPLICABLE" and view["gap_occurrences"] == []


def test_numeric_tolerance_missing_paths_and_boolean_type():
    a = lambda p, v, **kw: {
        "path": [p],
        "equals": v,
        "reference": "independent table",
        **kw,
    }
    differences = compare_assertions(
        {"x": 1.00001, "b": True},
        [a("x", 1, absolute_tolerance=0.001), a("b", 1), a("missing", None)],
    )
    assert len(differences) == 2 and differences[-1]["missing_path"] is True


def test_hash_failure_does_not_create_output(tmp_path):
    path, cat = one_case(tmp_path)
    cat["cases"][0]["inputs"]["request"]["sha256"] = "0" * 64
    path.write_text(json.dumps(cat))
    out = tmp_path / "run"
    assert main(["--catalog", str(path), "--output-dir", str(out)]) == 2
    assert not out.exists()


def test_differences_fail_without_rewriting_expected_values(tmp_path):
    path, cat = one_case(tmp_path)
    cat["cases"][0]["assertions"][0]["equals"] = "incorrect-version"
    path.write_text(json.dumps(cat))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    out = tmp_path / "run"
    assert main(["--catalog", str(path), "--output-dir", str(out)]) == 1
    result = json.loads((out / "summary.json").read_text())
    assert result["cases"][0]["differences"][0]["actual"] == "4"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert main(["--catalog", str(path), "--output-dir", str(out)]) == 2


@pytest.mark.parametrize(
    "change", ["duplicate", "unsafe-id", "reviewed-without-record", "bad-tolerance"]
)
def test_catalog_rejects_ambiguous_or_false_review_metadata(tmp_path, change):
    path, cat = one_case(tmp_path)
    case = cat["cases"][0]
    if change == "duplicate":
        cat["cases"].append(deepcopy(case))
    elif change == "unsafe-id":
        case["case_id"] = "../input"
    elif change == "reviewed-without-record":
        case["review"]["status"] = "REVIEWED"
    else:
        case["assertions"][0]["absolute_tolerance"] = -1
    path.write_text(json.dumps(cat))
    with pytest.raises(ValueError):
        load_catalog(path)


def test_raw_capture_tampering_rejected_before_reports(tmp_path):
    import shutil

    path, cat = one_case(tmp_path)
    archive = tmp_path / "archive"
    shutil.copytree(ROOT / "examples/confirmed_line/archive", archive)
    cat["cases"][0]["inputs"]["archive_replay"]["path"] = str(archive / "manifest.json")
    path.write_text(json.dumps(cat))
    raw = archive / "response-2.xml"
    raw.write_bytes(raw.read_bytes() + b"\n")
    out = tmp_path / "run"
    assert main(["--catalog", str(path), "--output-dir", str(out)]) == 2
    assert not out.exists()
