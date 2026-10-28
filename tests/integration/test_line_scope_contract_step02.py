"""Step 02 wire scope reservation: fail closed before submitted-line science exists.

Only the legacy LINE evaluator is executable in this step. No network or new
scientific aggregation is exercised by these tests.
"""
from dataclasses import replace

import pytest

from alma_duplicate.assessment import AssessmentStatus, assess_observation
from alma_duplicate.domain.proposed_observation import (
    LINE_SCOPE_LEGACY, LINE_SCOPE_SUBMITTED,
)
from alma_duplicate.line_pairing import build_line_pairs
from alma_duplicate.reporting import json_value
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.line import evaluate_line
from alma_duplicate.ui.proposed import build_document, validate_form
from tests.integration.test_line_evaluation import evaluate as evaluate_single
from tests.integration.test_line_evaluation import sky_request
from tests.integration.test_line_preparation import payload, report
from tests.integration.test_mosaic_scientific_acceptance import _line_case


@pytest.mark.parametrize("complete", [False, True])
def test_omitted_scope_preserves_legacy_request_shape_and_semantics(complete):
    document = sky_request(240)
    document["request"]["setup_complete"] = complete
    parsed = validate_proposed_observation(document["request"], document["search_options"])
    assert parsed.is_valid, parsed.errors
    assert parsed.request.line_evaluation_scope == LINE_SCOPE_LEGACY
    assert "line_evaluation_scope" not in parsed.raw_input
    serialized = json_value(parsed.request)
    assert "line_evaluation_scope" not in serialized
    assert "line_evaluation_scope" not in serialized["raw_input"]

    # Compare against the same concrete replay, once with an explicit legacy marker.
    # The helper supplies the same recorded Archive response in both runs.
    from alma_duplicate.candidate_search import search_candidates
    from alma_duplicate.clients.archive_replay import RecordedArchiveClient
    from tests.integration.test_line_preparation import EXAMPLE, validate
    archive = search_candidates(
        validate(), archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json")
    ).archive.source_record
    legacy = evaluate_single(archive, document).context_evaluations[0]
    explicit = sky_request(240)
    explicit["request"].update(setup_complete=complete, line_evaluation_scope=LINE_SCOPE_LEGACY)
    marked = evaluate_single(archive, explicit).context_evaluations[0]
    assert [(p.truth, p.method_version) for p in legacy.line_pairs] == [
        (p.truth, p.method_version) for p in marked.line_pairs
    ]
    assert legacy.branches == marked.branches
    assert legacy.branches[0].method_version == "archive_line_context_or_1"


@pytest.mark.parametrize("scope,code", [
    (LINE_SCOPE_SUBMITTED, "LINE_SCOPE_NOT_IMPLEMENTED"),
    ("UNKNOWN_FUTURE_SCOPE", "INVALID_CHOICE"),
    (None, "REQUIRED_FIELD"),
    (True, "INVALID_CHOICE"),
    (LINE_SCOPE_LEGACY.lower(), "INVALID_CHOICE"),
])
def test_unimplemented_or_malformed_explicit_scope_is_validation_error(scope, code):
    document = payload()
    document["request"]["line_evaluation_scope"] = scope
    parsed = validate_proposed_observation(document["request"], document["search_options"])
    assert not parsed.is_valid
    assert not parsed.can_search
    assert parsed.request is None
    assert any(i.path == "request.line_evaluation_scope" and i.code == code
               for i in parsed.errors)


def test_future_scope_blocked_at_assessment_boundary_without_source_access():
    document = payload()
    document["request"]["line_evaluation_scope"] = LINE_SCOPE_SUBMITTED
    result = assess_observation(document["request"], document["search_options"])
    assert result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
    assert result.document is None
    assert any(i.code == "LINE_SCOPE_NOT_IMPLEMENTED" for i in result.validation.errors)


def test_mixed_line_and_continuum_future_scope_is_also_rejected():
    document = payload()
    document["request"]["intents"] = ["LINE", "CONTINUUM"]
    document["request"]["line_evaluation_scope"] = LINE_SCOPE_SUBMITTED
    parsed = validate_proposed_observation(document["request"], document["search_options"])
    assert not parsed.is_valid
    assert any(i.code == "LINE_SCOPE_NOT_IMPLEMENTED" for i in parsed.errors)


def test_browser_legacy_mapping_is_unchanged_and_explicit_future_scope_is_not_discarded():
    from tests.ui.test_proposed import fields, ROW
    values = fields() | {"intents": ["LINE"], "sources": ["ARCHIVE"]}
    legacy, _ = build_document(values, [ROW])
    assert "line_evaluation_scope" not in legacy["request"]
    _, validation, _ = validate_form(values, [ROW])
    assert validation.is_valid and validation.can_search

    values["line_evaluation_scope"] = LINE_SCOPE_SUBMITTED
    document, validation, form_issues = validate_form(values, [ROW])
    assert document["request"]["line_evaluation_scope"] == LINE_SCOPE_SUBMITTED
    assert not validation.is_valid and not validation.can_search
    assert any(i["issue"].code == "LINE_SCOPE_NOT_IMPLEMENTED"
               and i["field"] == "line_evaluation_scope" for i in form_issues)


@pytest.mark.parametrize("geometry", ["single", "mosaic"])
def test_direct_science_callers_cannot_bypass_scope_validation(geometry):
    if geometry == "single":
        item = report().context_evaluations[0]
        request = report().search_result.plan.validation.request
        context = item.candidate.context
        common = tuple(item.criteria)
    else:
        request, context, pointings, execution, array = _line_case()
        # The direct Mosaic entrypoint normally builds the position criterion.
        from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
        request = replace(request, raw_input={
            **request.raw_input, "line_evaluation_scope": LINE_SCOPE_SUBMITTED,
        })
        with pytest.raises(ValueError, match="LINE_SCOPE_NOT_IMPLEMENTED"):
            evaluate_mosaic_context(request, context, pointings,
                                    executions=[execution], array_evidence=array)
        with pytest.raises(ValueError, match="LINE_SCOPE_NOT_IMPLEMENTED"):
            build_line_pairs(request, context, mosaic=True)
        return
    request = replace(request, raw_input={
        **request.raw_input, "line_evaluation_scope": LINE_SCOPE_SUBMITTED,
    })
    with pytest.raises(ValueError, match="LINE_SCOPE_NOT_IMPLEMENTED"):
        evaluate_line(request, context, common)
    with pytest.raises(ValueError, match="LINE_SCOPE_NOT_IMPLEMENTED"):
        build_line_pairs(request, context)
